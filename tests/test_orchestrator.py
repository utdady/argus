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
