from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

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


def run_case(orch: Orchestrator, case: dict) -> tuple[bool, str, float, dict]:
    # Isolate memory between cases so order does not leak.
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
        reply = result.reply.lower()
        ok = (
            "deny" in decisions
            or "denied" in reply
            or "allowlist" in reply
            or ("cannot" in reply and "open" in reply)
        )
        detail = f"decisions={decisions} reply={result.reply[:80]!r}"
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
        "--save",
        type=Path,
        default=Path(__file__).with_name("results") / "latest.json",
        help="Write JSON results (default: evals/results/latest.json)",
    )
    args = parser.parse_args()

    settings = load_settings()
    model = args.model or settings.model

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

    print(f"model={model} cases={len(cases)}")
    passed = 0
    latencies: list[float] = []
    records: list[dict] = []
    for case in cases:
        ok, detail, elapsed, record = run_case(orch, case)
        latencies.append(elapsed)
        records.append(record)
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"{mark} {case['id']:20s} {elapsed:6.2f}s  {detail}")

    total = len(cases)
    rate = (passed / total * 100) if total else 0.0
    avg = sum(latencies) / len(latencies) if latencies else 0.0
    print()
    print(f"pass_rate={passed}/{total} ({rate:.1f}%)  avg_latency={avg:.2f}s")

    payload = {
        "model": model,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "pass_rate": f"{passed}/{total}",
        "pass_pct": round(rate, 1),
        "avg_latency_s": round(avg, 2),
        "cases": records,
    }
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"saved {args.save}")

    store.close()
    try:
        db_path.unlink(missing_ok=True)
    except OSError:
        pass
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
