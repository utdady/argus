from __future__ import annotations

import argparse
import sys
import uuid

from argus.config import load_settings
from argus.orchestrator.loop import Orchestrator
from argus.permissions.policy import PermissionPolicy
from argus.providers.openai_compat import OpenAICompatProvider
from argus.storage.db import Storage
from argus.tools.builtin import build_builtin_registry


def build_orchestrator() -> tuple[Orchestrator, Storage]:
    settings = load_settings()
    store = Storage(settings.db_path)
    llm = OpenAICompatProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.model,
        num_ctx=settings.num_ctx,
        timeout_s=settings.request_timeout_s,
        default_temperature=settings.temperature,
    )
    orch = Orchestrator(
        settings=settings,
        llm=llm,
        registry=build_builtin_registry(),
        store=store,
        policy=PermissionPolicy(),
    )
    return orch, store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Argus V0 brain CLI")
    parser.add_argument(
        "--session",
        default=None,
        help="Reuse a session id (default: new)",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    orch, store = build_orchestrator()
    session_id = args.session or uuid.uuid4().hex
    store.create_session(session_id, settings.user_id, settings.device_id)

    print(f"Argus CLI — model={settings.model} db={settings.db_path}")
    print(f"session={session_id}")
    print("Commands: /confirm yes|no [token], /quit")
    print()

    pending_token: str | None = None
    try:
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.lower() in {"/quit", "/exit", "quit", "exit"}:
                break

            if line.lower().startswith("/confirm"):
                parts = line.split()
                if len(parts) < 2:
                    print("argus> usage: /confirm yes|no [token]")
                    continue
                approved = parts[1].lower() in {"yes", "y", "true", "1"}
                token = parts[2] if len(parts) > 2 else pending_token
                if not token:
                    print("argus> no confirm token; pass token explicitly")
                    continue
                result = orch.resolve_confirm(session_id, token, approved)
                pending_token = result.confirm_token
                print(f"argus> [{result.status}] {result.reply}")
                continue

            result = orch.handle_user_message(session_id, line)
            pending_token = result.confirm_token
            print(f"argus> [{result.status}] {result.reply}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
