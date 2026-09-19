from __future__ import annotations

import pytest

from argus.permissions.policy import Decision, PermissionPolicy
from argus.tools.builtin import ALLOWED_APPS, build_builtin_registry
from argus.tools.registry import Risk, ToolSpec
from pydantic import BaseModel


class _Dummy(BaseModel):
    x: int = 1


def test_builtin_tools_registered():
    reg = build_builtin_registry()
    names = {s.name for s in reg.list_specs()}
    assert names == {"get_time", "remember", "recall", "open_application"}


def test_validate_get_time_empty():
    reg = build_builtin_registry()
    args = reg.validate_args("get_time", {})
    assert args.model_dump() == {}


def test_validate_remember():
    reg = build_builtin_registry()
    args = reg.validate_args("remember", {"content": "hello", "source": "user"})
    assert args.content == "hello"


def test_validate_remember_rejects_empty():
    reg = build_builtin_registry()
    with pytest.raises(ValueError):
        reg.validate_args("remember", {"content": ""})


def test_validate_malformed_json_flag():
    reg = build_builtin_registry()
    with pytest.raises(ValueError, match="malformed"):
        reg.validate_args("get_time", {"_parse_error": True, "_raw": "{"})


def test_unknown_tool():
    reg = build_builtin_registry()
    with pytest.raises(KeyError):
        reg.validate_args("shell", {"cmd": "ls"})


def test_openai_schema_shape():
    reg = build_builtin_registry()
    tools = reg.openai_tools()
    assert all(t["type"] == "function" for t in tools)
    assert {t["function"]["name"] for t in tools} == {
        "get_time",
        "remember",
        "recall",
        "open_application",
    }


def test_open_application_allowlist():
    assert "notepad" in ALLOWED_APPS
    assert "rm" not in ALLOWED_APPS


def test_permission_allow_read():
    reg = build_builtin_registry()
    spec = reg.get("get_time")
    policy = PermissionPolicy()
    result = policy.decide(spec, role="owner")
    assert result.decision == Decision.ALLOW


def test_permission_confirm_side_effect():
    reg = build_builtin_registry()
    spec = reg.get("open_application")
    assert spec is not None
    assert spec.risk == Risk.SIDE_EFFECT
    policy = PermissionPolicy()
    result = policy.decide(spec, role="owner")
    assert result.decision == Decision.CONFIRM


def test_permission_deny_unknown():
    policy = PermissionPolicy()
    result = policy.decide(None, role="owner")
    assert result.decision == Decision.DENY


def test_permission_deny_wrong_role():
    spec = ToolSpec(
        name="secret",
        description="x",
        input_model=_Dummy,
        risk=Risk.READ,
        requires_confirm=False,
        allowed_roles=["owner"],
        execute=lambda a, c: "ok",
    )
    policy = PermissionPolicy()
    result = policy.decide(spec, role="guest")
    assert result.decision == Decision.DENY
