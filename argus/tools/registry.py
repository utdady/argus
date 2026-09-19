from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class Risk(str, Enum):
    READ = "read"
    WRITE = "write"
    SIDE_EFFECT = "side_effect"


@dataclass
class ToolContext:
    user_id: str
    role: str
    device_id: str
    session_id: str
    store: Any  # Storage — typed loosely to avoid cycles


ExecuteFn = Callable[[BaseModel, ToolContext], str]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    risk: Risk
    requires_confirm: bool
    allowed_roles: list[str] = field(default_factory=lambda: ["owner"])
    execute: ExecuteFn | None = None

    def openai_schema(self) -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        # OpenAI tools expect parameters without $defs noise when possible
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool: {spec.name}")
        if spec.execute is None:
            raise ValueError(f"tool {spec.name} missing execute")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def openai_tools(self, allowed_names: set[str] | None = None) -> list[dict[str, Any]]:
        specs = self._tools.values()
        if allowed_names is not None:
            specs = [s for s in specs if s.name in allowed_names]
        return [s.openai_schema() for s in specs]

    def validate_args(self, name: str, arguments: dict[str, Any]) -> BaseModel:
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"unknown tool: {name}")
        if arguments.get("_parse_error"):
            raise ValueError("malformed JSON arguments from model")
        try:
            return spec.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def run(self, name: str, args: BaseModel, ctx: ToolContext) -> str:
        spec = self._tools[name]
        assert spec.execute is not None
        return spec.execute(args, ctx)
