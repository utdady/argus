from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.tools.registry import Risk, ToolContext, ToolRegistry, ToolSpec

# Allowlisted app names for dry-run confirm path (no real launch in V0).
ALLOWED_APPS = frozenset({"notepad", "calculator", "explorer", "vscode", "chrome"})


class GetTimeInput(BaseModel):
    """No parameters."""

    model_config = ConfigDict(extra="forbid")


class RememberInput(BaseModel):
    content: str = Field(..., min_length=1, description="Fact or note to store")
    source: Literal["user", "tool"] = Field(
        default="user",
        description="Provenance: user-said vs tool-derived",
    )


class RecallInput(BaseModel):
    query: str = Field(..., min_length=1, description="Search query for notes")
    limit: int = Field(default=5, ge=1, le=20)


class OpenApplicationInput(BaseModel):
    app: str = Field(..., description=f"Allowlisted app name: {sorted(ALLOWED_APPS)}")


def _get_time(_args: GetTimeInput, _ctx: ToolContext) -> str:
    now = datetime.now(timezone.utc).astimezone()
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


def _remember(args: RememberInput, ctx: ToolContext) -> str:
    note_id = ctx.store.add_note(
        content=args.content,
        user_id=ctx.user_id,
        source=args.source,
    )
    return f"Saved note #{note_id}."


def _recall(args: RecallInput, ctx: ToolContext) -> str:
    rows = ctx.store.search_notes(args.query, user_id=ctx.user_id, limit=args.limit)
    if not rows:
        return "No matching notes."
    lines = [f"#{r['id']} [{r['source']}] {r['content']}" for r in rows]
    return "\n".join(lines)


def _open_application(args: OpenApplicationInput, _ctx: ToolContext) -> str:
    app = args.app.strip().lower()
    if app not in ALLOWED_APPS:
        return f"Denied: '{args.app}' is not in the allowlist {sorted(ALLOWED_APPS)}."
    # Dry-run: do not launch processes in V0.
    return f"[dry-run] Would open application '{app}'."


def build_builtin_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        ToolSpec(
            name="get_time",
            description="Return the current local date and time.",
            input_model=GetTimeInput,
            risk=Risk.READ,
            requires_confirm=False,
            execute=_get_time,
        )
    )
    reg.register(
        ToolSpec(
            name="remember",
            description="Store a durable note/fact for later recall.",
            input_model=RememberInput,
            risk=Risk.WRITE,
            requires_confirm=False,
            execute=_remember,
        )
    )
    reg.register(
        ToolSpec(
            name="recall",
            description="Search stored notes by keyword.",
            input_model=RecallInput,
            risk=Risk.READ,
            requires_confirm=False,
            execute=_recall,
        )
    )
    reg.register(
        ToolSpec(
            name="open_application",
            description=(
                "Request opening an allowlisted desktop application. "
                "Requires user confirmation. Dry-run only in V0."
            ),
            input_model=OpenApplicationInput,
            risk=Risk.SIDE_EFFECT,
            requires_confirm=True,
            execute=_open_application,
        )
    )
    return reg
