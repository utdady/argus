from __future__ import annotations

from pathlib import Path

from argus.config import Settings
from argus.orchestrator.loop import Orchestrator
from argus.permissions.policy import PermissionPolicy
from argus.providers.base import Message, ToolCall
from argus.storage.db import Storage
from argus.tools.builtin import build_builtin_registry


class ScriptedLLM:
    """Deterministic LLM that returns scripted Messages and records inputs."""

    def __init__(self, script: list[Message]) -> None:
        self._script = list(script)
        self.calls: list[list[Message]] = []

    def complete(
        self,
        messages: list[Message],
        tools: list | None = None,
        *,
        temperature: float | None = None,
    ) -> Message:
        self.calls.append(list(messages))
        if not self._script:
            raise AssertionError("ScriptedLLM: no responses left")
        return self._script.pop(0)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_base_url="http://127.0.0.1:9/v1",
        llm_api_key="test",
        model="scripted",
        num_ctx=512,
        db_path=tmp_path / "orch.db",
        user_id="owner",
        user_role="owner",
        device_id="test_device",
    )


def _orch(tmp_path: Path, llm: ScriptedLLM) -> Orchestrator:
    settings = _settings(tmp_path)
    store = Storage(settings.db_path)
    return Orchestrator(
        settings=settings,
        llm=llm,
        registry=build_builtin_registry(),
        store=store,
        policy=PermissionPolicy(),
    )


def test_tool_calls_persist_across_user_turns(tmp_path: Path):
    llm = ScriptedLLM(
        [
            Message(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(id="call_time", name="get_time", arguments={}),
                ],
            ),
            Message(role="assistant", content="It is now."),
            Message(role="assistant", content="Still here."),
        ]
    )
    orch = _orch(tmp_path, llm)
    sid = orch.new_session()

    first = orch.handle_user_message(sid, "What time is it?")
    assert first.status == "completed"
    assert "It is now" in first.reply

    # Second user turn rebuilds history from DB — must include tool_calls.
    second = orch.handle_user_message(sid, "thanks")
    assert second.status == "completed"
    assert len(llm.calls) >= 3

    rebuilt = llm.calls[2]  # complete() for second user turn
    assistants_with_tools = [
        m for m in rebuilt if m.role == "assistant" and m.tool_calls
    ]
    assert assistants_with_tools, "expected persisted assistant tool_calls in history"
    assert assistants_with_tools[0].tool_calls[0].id == "call_time"
    tool_msgs = [m for m in rebuilt if m.role == "tool"]
    assert tool_msgs
    assert tool_msgs[0].tool_call_id == "call_time"


def test_confirm_resume_does_not_duplicate_tool_result(tmp_path: Path):
    llm = ScriptedLLM(
        [
            Message(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_open",
                        name="open_application",
                        arguments={"app": "notepad"},
                    ),
                ],
            ),
            Message(role="assistant", content="Opened (dry-run)."),
        ]
    )
    orch = _orch(tmp_path, llm)
    sid = orch.new_session()

    pending = orch.handle_user_message(sid, "Open notepad")
    assert pending.status == "awaiting_confirm"
    assert pending.confirm_token

    done = orch.resolve_confirm(sid, pending.confirm_token, True)
    assert done.status == "completed"
    assert "Opened" in done.reply

    # The continuation LLM call should see exactly one tool result for call_open.
    cont = llm.calls[-1]
    tool_msgs = [
        m for m in cont if m.role == "tool" and m.tool_call_id == "call_open"
    ]
    assert len(tool_msgs) == 1, f"expected 1 tool result, got {len(tool_msgs)}"

    assistants = [m for m in cont if m.role == "assistant" and m.tool_calls]
    assert assistants
    assert assistants[-1].tool_calls[0].id == "call_open"


def test_history_starts_at_user_boundary(tmp_path: Path):
    """Row-limited windows must not start on an orphan tool result."""
    settings = _settings(tmp_path)
    # Tiny window: only last 1 user turn kept.
    settings = Settings(
        llm_base_url="http://127.0.0.1:9/v1",
        llm_api_key="test",
        model="scripted",
        num_ctx=512,
        db_path=tmp_path / "hist.db",
        user_id="owner",
        user_role="owner",
        device_id="test_device",
        max_history_user_turns=1,
    )
    llm = ScriptedLLM(
        [
            Message(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="t1", name="get_time", arguments={})],
            ),
            Message(role="assistant", content="first time"),
            # Simulate a truncated/empty turn that only stores one assistant row
            # by returning empty then a final reply on retry — but for history we
            # also plant an orphan manually after first exchange.
            Message(role="assistant", content=""),  # will retry
            Message(role="assistant", content="ok"),
            Message(role="assistant", content="latest"),
        ]
    )
    store = Storage(settings.db_path)
    orch = Orchestrator(
        settings=settings,
        llm=llm,
        registry=build_builtin_registry(),
        store=store,
        policy=PermissionPolicy(),
    )
    sid = orch.new_session()
    orch.handle_user_message(sid, "time please")
    # Orphan: tool result without its assistant call in a narrow row window.
    store.add_message(sid, "assistant", "(timed out)")
    store.add_message(sid, "tool", "orphan-result", tool_call_id="missing")
    orch.handle_user_message(sid, "hello again")

    rebuilt = llm.calls[-1]
    # Must start (after system) at a user message, never a lone tool.
    non_system = [m for m in rebuilt if m.role != "system"]
    assert non_system[0].role == "user"
    assert non_system[0].content == "hello again"
    # Orphan from previous truncated turn must not appear without its call.
    assert not any(m.role == "tool" and m.content == "orphan-result" for m in rebuilt)


def test_mid_batch_confirm_skips_remaining_calls(tmp_path: Path):
    llm = ScriptedLLM(
        [
            Message(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(id="a", name="get_time", arguments={}),
                    ToolCall(
                        id="b",
                        name="open_application",
                        arguments={"app": "notepad"},
                    ),
                    ToolCall(id="c", name="get_time", arguments={}),
                ],
            ),
            Message(role="assistant", content="done after confirm"),
        ]
    )
    orch = _orch(tmp_path, llm)
    sid = orch.new_session()
    pending = orch.handle_user_message(sid, "time then open notepad then time")
    assert pending.status == "awaiting_confirm"
    assert pending.pending_tool == "open_application"

    rows = orch.store.list_messages(sid, limit=50)
    tool_ids = [r["tool_call_id"] for r in rows if r["role"] == "tool"]
    assert "a" in tool_ids
    assert "c" in tool_ids  # skipped placeholder, not left hanging
    skip_row = next(r for r in rows if r["role"] == "tool" and r["tool_call_id"] == "c")
    assert "skipped" in skip_row["content"]

    done = orch.resolve_confirm(sid, pending.confirm_token, True)
    assert done.status == "completed"


def test_empty_reply_retries_then_errors(tmp_path: Path):
    llm = ScriptedLLM(
        [
            Message(role="assistant", content=""),
            Message(role="assistant", content=""),
        ]
    )
    settings = Settings(
        llm_base_url="http://127.0.0.1:9/v1",
        llm_api_key="test",
        model="scripted",
        num_ctx=512,
        db_path=tmp_path / "empty.db",
        user_id="owner",
        user_role="owner",
        device_id="test_device",
        empty_reply_retries=1,
    )
    store = Storage(settings.db_path)
    orch = Orchestrator(
        settings=settings,
        llm=llm,
        registry=build_builtin_registry(),
        store=store,
        policy=PermissionPolicy(),
    )
    sid = orch.new_session()
    result = orch.handle_user_message(sid, "hi")
    assert result.status == "error"
    assert "empty" in result.reply.lower()
    assert len(llm.calls) == 2
    # Retry must change the request (ephemeral nudge), not replay identical input.
    assert any(
        m.role == "user" and "empty" in (m.content or "").lower()
        for m in llm.calls[1]
    )
    # Nudge must not be persisted.
    persisted = store.list_messages(sid)
    assert not any(
        m["role"] == "user" and "empty" in (m["content"] or "").lower()
        for m in persisted
        if m["content"] != "hi"
    )


def test_empty_reply_recovers_on_retry(tmp_path: Path):
    llm = ScriptedLLM(
        [
            Message(role="assistant", content="  "),
            Message(role="assistant", content="Hello."),
        ]
    )
    orch = _orch(tmp_path, llm)
    sid = orch.new_session()
    result = orch.handle_user_message(sid, "hi")
    assert result.status == "completed"
    assert result.reply == "Hello."
    assert any(
        m.role == "user" and "empty" in (m.content or "").lower()
        for m in llm.calls[1]
    )
