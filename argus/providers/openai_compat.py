from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from argus.providers.base import Message, ToolCall


class OpenAICompatProvider:
    """OpenAI SDK pointed at Ollama (or any OpenAI-compatible base_url)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        num_ctx: int = 4096,
        timeout_s: float = 120.0,
        default_temperature: float = 0.0,
    ) -> None:
        self.model = model
        self.num_ctx = num_ctx
        self.default_temperature = default_temperature
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s)

    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float | None = None,
    ) -> Message:
        payload = [_to_openai_message(m) for m in messages]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": payload,
            "temperature": self.default_temperature if temperature is None else temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        # Ollama reads num_ctx via extra_body / options
        kwargs["extra_body"] = {"options": {"num_ctx": self.num_ctx}}

        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message
        tool_calls: list[ToolCall] = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                raw = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw)
                except json.JSONDecodeError:
                    args = {"_raw": raw, "_parse_error": True}
                if not isinstance(args, dict):
                    args = {"_raw": args, "_parse_error": True}
                tool_calls.append(
                    ToolCall(id=tc.id or "", name=tc.function.name or "", arguments=args)
                )
        return Message(
            role="assistant",
            content=choice.content,
            tool_calls=tool_calls,
        )


def _to_openai_message(m: Message) -> dict[str, Any]:
    if m.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": m.tool_call_id or "",
            "content": m.content or "",
        }
    if m.role == "assistant" and m.tool_calls:
        return {
            "role": "assistant",
            "content": m.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ],
        }
    return {"role": m.role, "content": m.content or ""}
