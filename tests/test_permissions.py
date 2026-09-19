from __future__ import annotations

from argus.permissions.policy import Decision, PermissionPolicy
from argus.tools.builtin import build_builtin_registry


def test_matrix_owner_read_write_side_effect():
    reg = build_builtin_registry()
    policy = PermissionPolicy()

    assert policy.decide(reg.get("get_time"), role="owner").decision == Decision.ALLOW
    assert policy.decide(reg.get("remember"), role="owner").decision == Decision.ALLOW
    assert policy.decide(reg.get("recall"), role="owner").decision == Decision.ALLOW
    assert (
        policy.decide(reg.get("open_application"), role="owner").decision
        == Decision.CONFIRM
    )


def test_guest_denied_all_builtins():
    reg = build_builtin_registry()
    policy = PermissionPolicy()
    for spec in reg.list_specs():
        assert policy.decide(spec, role="guest").decision == Decision.DENY
