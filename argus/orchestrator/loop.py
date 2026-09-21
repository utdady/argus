from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from argus.config import Settings
from argus.permissions.policy import Decision, PermissionPolicy
from argus.providers.base import LLMProvider, Message, ToolCall
from argus.storage.db import Storage
from argus.tools.registry import ToolContext, ToolRegistry

SYSTEM_PROMPT = """You are Argus, a helpful personal assistant running locally.
Use tools when they help answer accurately. Prefer concise replies.
Available tools are provided via function calling - only call tools that exist.
Do not invent tool names. If a side-effect tool needs confirmation, the system will pause.
"""

_SKIPPED_WAITING = json.dumps(
    {"ok": False, "error": "skipped, waiting for confirmation of another tool"}
)

_EMPTY_NUDGE = (
    "Your previous reply was empty. Respond with visible assistant text "
    "or a tool call now. Do not answer with only internal reasoning."
)


@dataclass
class TurnResult:
    status: str  # completed | awaiting_confirm | error
    reply: str
    confirm_token: str | None = None
    pending_tool: str | None = None
    pending_args: dict[str, Any] | None = None


class Orchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        llm: LLMProvider,
        registry: ToolRegistry,
        store: Storage,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.registry = registry
        self.store = store
        self.policy = policy or PermissionPolicy()

    def new_session(self) -> str:
        session_id = uuid.uuid4().hex
        self.store.create_session(
            session_id,
            self.settings.user_id,
            self.settings.device_id,
        )
        return session_id

    def handle_user_message(self, session_id: str, text: str) -> TurnResult:
        self.store.create_session(
            session_id,
            self.settings.user_id,
            self.settings.device_id,
        )
        pending = self.store.get_pending(session_id)
        if pending:
            return TurnResult(
                status="awaiting_confirm",
                reply=(
                    f"Pending confirmation for `{pending.tool_name}` "
                    f"args={pending.arguments}. Use /confirm yes|no "
                    f"(token {pending.token})."
                ),
                confirm_token=pending.token,
                pending_tool=pending.tool_name,
                pending_args=pending.arguments,
            )

        self.store.add_message(session_id, "user", text)
        messages = self._build_messages(session_id)
        return self._run_loop(session_id, messages)

    def resolve_confirm(self, session_id: str, token: str, approved: bool) -> TurnResult:
        pending = self.store.get_pending_by_token(token)
        if pending is None or pending.session_id != session_id:
            return TurnResult(status="error", reply="No matching pending confirmation.")

        self.store.clear_pending(session_id)
        ctx = self._tool_context(session_id)
        spec = self.registry.get(pending.tool_name)

        if not approved:
            self.store.audit(
                session_id=session_id,
                user_id=self.settings.user_id,
                device_id=self.settings.device_id,
                tool_name=pending.tool_name,
                arguments=pending.arguments,
                decision="cancel",
                outcome="user rejected",
            )
            tool_msg = Message(
                role="tool",
                content=json.dumps({"ok": False, "error": "user rejected confirmation"}),
                tool_call_id=pending.tool_call_id,
                name=pending.tool_name,
            )
            self.store.add_message(
                session_id,
                "tool",
                tool_msg.content,
                tool_call_id=pending.tool_call_id,
            )
            messages = self._build_messages(session_id)
            return self._run_loop(session_id, messages)

        if spec is None:
            return TurnResult(status="error", reply=f"Unknown tool {pending.tool_name}.")

        try:
            args = self.registry.validate_args(pending.tool_name, pending.arguments)
            outcome = self.registry.run(pending.tool_name, args, ctx)
            decision = "allow"
        except Exception as exc:  # noqa: BLE001
            outcome = f"error: {exc}"
            decision = "error"

        self.store.audit(
            session_id=session_id,
            user_id=self.settings.user_id,
            device_id=self.settings.device_id,
            tool_name=pending.tool_name,
            arguments=pending.arguments,
            decision=decision,
            outcome=outcome[:500],
        )
        tool_msg = Message(
            role="tool",
            content=outcome,
            tool_call_id=pending.tool_call_id,
            name=pending.tool_name,
        )
        self.store.add_message(
            session_id,
            "tool",
            tool_msg.content,
            tool_call_id=pending.tool_call_id,
        )
        messages = self._build_messages(session_id)
        return self._run_loop(session_id, messages)

    def _tool_context(self, session_id: str) -> ToolContext:
        return ToolContext(
            user_id=self.settings.user_id,
            role=self.settings.user_role,
            device_id=self.settings.device_id,
            session_id=session_id,
            store=self.store,
        )

    def _build_messages(self, session_id: str) -> list[Message]:
        messages: list[Message] = [Message(role="system", content=SYSTEM_PROMPT)]
        rows = self.store.load_history(
            session_id,
            max_user_turns=self.settings.max_history_user_turns,
        )
        for row in rows:
            role = row["role"]
            if role == "tool":
                messages.append(
                    Message(
                        role="tool",
                        content=row["content"],
                        tool_call_id=row["tool_call_id"],
                    )
                )
            elif role == "assistant":
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc.get("arguments") or {},
                    )
                    for tc in (row.get("tool_calls") or [])
                ]
                messages.append(
                    Message(
                        role="assistant",
                        content=row["content"],
                        tool_calls=tool_calls,
                    )
                )
            else:
                messages.append(Message(role=role, content=row["content"]))
        return messages

    @staticmethod
    def _serialize_tool_calls(tool_calls: list[ToolCall]) -> list[dict[str, Any]]:
        return [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
            for tc in tool_calls
        ]

    def _skip_remaining_tool_calls(
        self,
        session_id: str,
        messages: list[Message],
        remaining: list[ToolCall],
    ) -> None:
        """Answer sibling tool_calls so the provider never sees an unfinished batch."""
        for tc in remaining:
            self.store.audit(
                session_id=session_id,
                user_id=self.settings.user_id,
                device_id=self.settings.device_id,
                tool_name=tc.name,
                arguments=tc.arguments,
                decision="skip",
                outcome="waiting for confirmation of another tool",
            )
            tool_msg = Message(
                role="tool",
                content=_SKIPPED_WAITING,
                tool_call_id=tc.id,
                name=tc.name,
            )
            self.store.add_message(
                session_id, "tool", tool_msg.content, tool_call_id=tc.id
            )
            messages.append(tool_msg)

    def _run_loop(self, session_id: str, messages: list[Message]) -> TurnResult:
        ctx = self._tool_context(session_id)
        tools = self.registry.openai_tools()
        schema_retries_left = self.settings.schema_retries
        empty_retries_left = self.settings.empty_reply_retries
        call_temperature = self.settings.temperature

        for _ in range(self.settings.max_iterations):
            try:
                assistant = self.llm.complete(
                    messages,
                    tools=tools,
                    temperature=call_temperature,
                )
            except Exception as exc:  # noqa: BLE001
                return TurnResult(status="error", reply=f"LLM error: {exc}")
            # Reset override after each call; empty-retry may bump it again.
            call_temperature = self.settings.temperature

            if not assistant.tool_calls:
                text = (assistant.content or "").strip()
                if not text:
                    if empty_retries_left > 0:
                        empty_retries_left -= 1
                        # Ephemeral nudge — not persisted to session history.
                        messages = [
                            *messages,
                            Message(role="user", content=_EMPTY_NUDGE),
                        ]
                        call_temperature = max(self.settings.temperature, 0.2)
                        continue
                    return TurnResult(
                        status="error",
                        reply="LLM returned an empty reply after retries.",
                    )
                self.store.add_message(session_id, "assistant", text)
                return TurnResult(status="completed", reply=text)

            for tc in assistant.tool_calls:
                tc.id = tc.id or uuid.uuid4().hex

            self.store.add_message(
                session_id,
                "assistant",
                assistant.content,
                tool_calls=self._serialize_tool_calls(assistant.tool_calls),
            )
            messages.append(assistant)

            for idx, tc in enumerate(assistant.tool_calls):
                tc_id = tc.id
                spec = self.registry.get(tc.name)

                try:
                    args_model = self.registry.validate_args(tc.name, tc.arguments)
                    args_dict = args_model.model_dump()
                except (KeyError, ValueError) as exc:
                    self.store.audit(
                        session_id=session_id,
                        user_id=self.settings.user_id,
                        device_id=self.settings.device_id,
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        decision="deny",
                        outcome=f"validation: {exc}",
                    )
                    err = f"validation error: {exc}"
                    tool_msg = Message(
                        role="tool",
                        content=err,
                        tool_call_id=tc_id,
                        name=tc.name,
                    )
                    self.store.add_message(session_id, "tool", err, tool_call_id=tc_id)
                    messages.append(tool_msg)
                    if schema_retries_left <= 0:
                        return TurnResult(
                            status="error",
                            reply=f"Tool validation failed repeatedly: {exc}",
                        )
                    schema_retries_left -= 1
                    continue

                perm = self.policy.decide(spec, role=self.settings.user_role)
                if perm.decision == Decision.DENY:
                    self.store.audit(
                        session_id=session_id,
                        user_id=self.settings.user_id,
                        device_id=self.settings.device_id,
                        tool_name=tc.name,
                        arguments=args_dict,
                        decision="deny",
                        outcome=perm.reason,
                    )
                    tool_msg = Message(
                        role="tool",
                        content=f"denied: {perm.reason}",
                        tool_call_id=tc_id,
                        name=tc.name,
                    )
                    self.store.add_message(
                        session_id, "tool", tool_msg.content, tool_call_id=tc_id
                    )
                    messages.append(tool_msg)
                    continue

                if perm.decision == Decision.CONFIRM:
                    token = self.store.set_pending(
                        session_id=session_id,
                        tool_name=tc.name,
                        arguments=args_dict,
                        tool_call_id=tc_id,
                        reason=perm.reason,
                    )
                    self.store.audit(
                        session_id=session_id,
                        user_id=self.settings.user_id,
                        device_id=self.settings.device_id,
                        tool_name=tc.name,
                        arguments=args_dict,
                        decision="confirm",
                        outcome="awaiting user",
                    )
                    # Close out the rest of this batch so history stays valid.
                    self._skip_remaining_tool_calls(
                        session_id,
                        messages,
                        assistant.tool_calls[idx + 1 :],
                    )
                    return TurnResult(
                        status="awaiting_confirm",
                        reply=(
                            f"Confirm `{tc.name}` with {args_dict}? "
                            f"Type `/confirm yes` or `/confirm no` (token {token})."
                        ),
                        confirm_token=token,
                        pending_tool=tc.name,
                        pending_args=args_dict,
                    )

                try:
                    outcome = self.registry.run(tc.name, args_model, ctx)
                except Exception as exc:  # noqa: BLE001
                    outcome = f"execution error: {exc}"
                self.store.audit(
                    session_id=session_id,
                    user_id=self.settings.user_id,
                    device_id=self.settings.device_id,
                    tool_name=tc.name,
                    arguments=args_dict,
                    decision="allow",
                    outcome=outcome[:500],
                )
                tool_msg = Message(
                    role="tool",
                    content=outcome,
                    tool_call_id=tc_id,
                    name=tc.name,
                )
                self.store.add_message(
                    session_id, "tool", tool_msg.content, tool_call_id=tc_id
                )
                messages.append(tool_msg)

        return TurnResult(
            status="error",
            reply="Stopped: max tool iterations reached.",
        )
