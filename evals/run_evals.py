from __future__ import annotations

import argparse
import json
import time
import uuid
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


def run_case(orch: Orchestrator, case: dict) -> tuple[bool, str, float]:
    session_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    result = orch.handle_user_message(session_id, case["prompt"])
    elapsed = time.perf_counter() - t0

    if case.get("expect_no_tool"):
        ok = result.status == "completed" and result.pending_tool is None
        rows = orch.store._conn.execute(
            "SELECT tool_name FROM tool_audit WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        if rows:
            ok = False
        detail = f"status={result.status} tools={[r['tool_name'] for r in rows]}"
        return ok, detail, elapsed

    if case.get("expect_deny"):
        rows = orch.store._conn.execute(
            "SELECT decision FROM tool_audit WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        decisions = [r["decision"] for r in rows]
        reply = result.reply.lower()
        ok = (
            "deny" in decisions
            or "denied" in reply
            or "allowlist" in reply
            or ("cannot" in reply and "open" in reply)
        )
        return ok, f"decisions={decisions} reply={result.reply[:80]!r}", elapsed

    expected = case.get("expect_tool")
    if case.get("expect_confirm") or expected == "open_application":
        ok = result.status == "awaiting_confirm" and (
            result.pending_tool == expected or (expected is None and result.pending_tool)
        )
        detail = f"status={result.status} pending={result.pending_tool}"
        return ok, detail, elapsed

    if expected:
        rows = orch.store._conn.execute(
            "SELECT tool_name, decision FROM tool_audit WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        names = [r["tool_name"] for r in rows]
        ok = expected in names and result.status in {"completed", "awaiting_confirm"}
        detail = f"tools={names} status={result.status}"
        return ok, detail, elapsed

    return True, "no expectation", elapsed


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
    for case in cases:
        ok, detail, elapsed = run_case(orch, case)
        latencies.append(elapsed)
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"{mark} {case['id']:20s} {elapsed:6.2f}s  {detail}")

    total = len(cases)
    rate = (passed / total * 100) if total else 0.0
    avg = sum(latencies) / len(latencies) if latencies else 0.0
    print()
    print(f"pass_rate={passed}/{total} ({rate:.1f}%)  avg_latency={avg:.2f}s")
    store.close()
    try:
        db_path.unlink(missing_ok=True)
    except OSError:
        pass
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
