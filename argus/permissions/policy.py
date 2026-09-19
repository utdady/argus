from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from argus.tools.registry import ToolSpec


class Decision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(frozen=True)
class PermissionResult:
    decision: Decision
    reason: str


class PermissionPolicy:
    """Authorization in code — never delegated to the LLM."""

    def decide(self, spec: ToolSpec | None, *, role: str) -> PermissionResult:
        if spec is None:
            return PermissionResult(Decision.DENY, "unknown tool")
        if role not in spec.allowed_roles:
            return PermissionResult(
                Decision.DENY,
                f"role '{role}' not in allowed_roles {spec.allowed_roles}",
            )
        if spec.requires_confirm:
            return PermissionResult(
                Decision.CONFIRM,
                f"tool '{spec.name}' requires confirmation (risk={spec.risk.value})",
            )
        return PermissionResult(Decision.ALLOW, "ok")
