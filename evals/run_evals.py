from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from argus.config import load_settings
from argus.orchestrator.loop import Orchestrator
from argus.permissions.policy import PermissionPolicy
from argus.providers.openai_compat import OpenAICompatProvider
from argus.storage.db import Storage
from argus.tools.builtin import build_builtin_registry


def load_cases(path: Path) -> list[dict]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


def _safe_model_name(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", model)


def run_case(orch: Orchestrator, case: dict) -> tuple[bool, str, float, dict]:
    orch.store.clear_notes()
    for note in case.get("seed_notes") or []:
        orch.store.add_note(note, user_id=orch.settings.user_id, source="user")

    session_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    result = orch.handle_user_message(session_id, case["prompt"])
    elapsed = time.perf_counter() - t0

    audit_rows = orch.store._conn.execute(
        "SELECT tool_name, decision, arguments_json, outcome FROM tool_audit WHERE session_id = ?",
        (session_id,),
    ).fetchall()
    audit = [dict(r) for r in audit_rows]
    record = {
        "id": case["id"],
        "ok": False,
        "elapsed_s": round(elapsed, 3),
        "status": result.status,
        "reply": result.reply,
        "pending_tool": result.pending_tool,
        "audit": audit,
    }

    if case.get("expect_no_tool"):
        ok = result.status == "completed" and result.pending_tool is None and not audit
        detail = f"status={result.status} tools={[r['tool_name'] for r in audit]}"
        record["ok"] = ok
        return ok, detail, elapsed, record

    if case.get("expect_deny"):
        decisions = [r["decision"] for r in audit]
        opened = any(
            r["tool_name"] == "open_application"
            and r["decision"] in {"allow", "confirm"}
            for r in audit
        )
        # Prefer structured signals over reply wording.
        ok = (not opened) and (
            "deny" in decisions
            or (
                result.status == "completed"
                and result.pending_tool is None
            )
        )
        detail = f"decisions={decisions} opened={opened} status={result.status}"
        record["ok"] = ok
        return ok, detail, elapsed, record

    expected = case.get("expect_tool")
    if case.get("expect_confirm") or expected == "open_application":
        ok = result.status == "awaiting_confirm" and (
            result.pending_tool == expected or (expected is None and result.pending_tool)
        )
        if ok and expected:
            ok = any(
                r["tool_name"] == expected and r["decision"] == "confirm" for r in audit
            )
        detail = f"status={result.status} pending={result.pending_tool}"
        record["ok"] = ok
        return ok, detail, elapsed, record

    if expected:
        allowed = [
            r
            for r in audit
            if r["tool_name"] == expected and r["decision"] in {"allow", "confirm"}
        ]
        ok = bool(allowed) and result.status in {"completed", "awaiting_confirm"}
        if ok and case.get("expect_args_contains"):
            blob = " ".join(r["arguments_json"] for r in allowed).lower()
            ok = all(s.lower() in blob for s in case["expect_args_contains"])
        if ok and case.get("expect_reply_contains"):
            reply = result.reply.lower()
            ok = all(s.lower() in reply for s in case["expect_reply_contains"])
        detail = (
            f"tools={[(r['tool_name'], r['decision']) for r in audit]} "
            f"status={result.status}"
        )
        record["ok"] = ok
        return ok, detail, elapsed, record

    record["ok"] = True
    return True, "no expectation", elapsed, record


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Argus tool-calling evals")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("cases.jsonl"),
    )
    parser.add_argument("--model", default=None, help="Override ARGUS_MODEL")
    parser.add_argument("--limit", type=int, default=0, help="Run first N cases (0=all)")
    parser.add_argument("--id", action="append", default=[], help="Run only case id(s)")
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Repeat each case N times (majority pass; records all runs)",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Write JSON results (default: evals/results/<model>.json)",
    )
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")

    settings = load_settings()
    model = args.model or settings.model
    save_path = args.save or (
        Path(__file__).with_name("results") / f"{_safe_model_name(model)}.json"
    )

    db_path = settings.db_path.parent / f"eval_{uuid.uuid4().hex}.db"
    store = Storage(db_path)
    llm = OpenAICompatProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=model,
        num_ctx=settings.num_ctx,
        timeout_s=settings.request_timeout_s,
        default_temperature=0.0,
    )
    orch = Orchestrator(
        settings=settings,
        llm=llm,
        registry=build_builtin_registry(),
        store=store,
        policy=PermissionPolicy(),
    )

    cases = load_cases(args.cases)
    if args.id:
        wanted = set(args.id)
        cases = [c for c in cases if c["id"] in wanted]
        missing = wanted - {c["id"] for c in cases}
        if missing:
            raise SystemExit(f"unknown case id(s): {sorted(missing)}")
    if args.limit > 0:
        cases = cases[: args.limit]

    print(f"model={model} cases={len(cases)} repeats={args.repeats}")
    case_summaries: list[dict] = []
    all_latencies: list[float] = []
    passed_cases = 0

    for case in cases:
        runs: list[dict] = []
        for i in range(args.repeats):
            ok, detail, elapsed, record = run_case(orch, case)
            record["repeat"] = i + 1
            record["detail"] = detail
            runs.append(record)
            all_latencies.append(elapsed)
            mark = "PASS" if ok else "FAIL"
            suffix = f" r{i+1}/{args.repeats}" if args.repeats > 1 else ""
            print(f"{mark} {case['id']:20s}{suffix} {elapsed:6.2f}s  {detail}")

        wins = sum(1 for r in runs if r["ok"])
        # Majority pass; ties (even repeats) require > half.
        case_ok = wins * 2 > args.repeats
        if case_ok:
            passed_cases += 1
        case_summaries.append(
            {
                "id": case["id"],
                "ok": case_ok,
                "wins": wins,
                "repeats": args.repeats,
                "runs": runs,
            }
        )

    total = len(cases)
    rate = (passed_cases / total * 100) if total else 0.0
    lat_sorted = sorted(all_latencies)
    p95 = lat_sorted[int(0.95 * (len(lat_sorted) - 1))] if lat_sorted else 0.0
    avg = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0
    med = median(all_latencies) if all_latencies else 0.0
    print()
    print(
        f"pass_rate={passed_cases}/{total} ({rate:.1f}%)  "
        f"avg={avg:.2f}s median={med:.2f}s p95={p95:.2f}s max={max(all_latencies, default=0):.2f}s"
    )

    payload = {
        "model": model,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "repeats": args.repeats,
        "pass_rate": f"{passed_cases}/{total}",
        "pass_pct": round(rate, 1),
        "latency_s": {
            "avg": round(avg, 2),
            "median": round(med, 2),
            "p95": round(p95, 2),
            "max": round(max(all_latencies, default=0), 2),
        },
        "cases": case_summaries,
    }
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Local convenience pointer only (gitignored) — commit per-model files.
    latest = Path(__file__).with_name("results") / "latest.json"
    latest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"saved {save_path}")

    store.close()
    try:
        db_path.unlink(missing_ok=True)
    except OSError:
        pass
    return 0 if passed_cases == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
