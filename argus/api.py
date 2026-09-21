from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from argus.config import load_settings
from argus.factory import build_orchestrator
from argus.orchestrator.loop import Orchestrator, TurnResult

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ConfirmRequest(BaseModel):
    session_id: str
    approved: bool
    token: str | None = None


class TurnResponse(BaseModel):
    session_id: str
    status: str
    reply: str
    confirm_token: str | None = None
    pending_tool: str | None = None
    pending_args: dict[str, Any] | None = None


def _to_response(session_id: str, result: TurnResult) -> TurnResponse:
    return TurnResponse(
        session_id=session_id,
        status=result.status,
        reply=result.reply,
        confirm_token=result.confirm_token,
        pending_tool=result.pending_tool,
        pending_args=result.pending_args,
    )


def create_app(orch: Orchestrator | None = None) -> FastAPI:
    """Build the FastAPI app. Pass orch in tests to avoid a live LLM."""
    injected = orch

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if injected is not None:
            app.state.orch = injected
            app.state.owns_store = False
        else:
            built, _store = build_orchestrator()
            app.state.orch = built
            app.state.owns_store = True
        yield
        if getattr(app.state, "owns_store", False):
            app.state.orch.store.close()

    app = FastAPI(title="Argus", version="0.1.0", lifespan=lifespan)
    # Eager bind for TestClient (lifespan may not run without context manager).
    if injected is not None:
        app.state.orch = injected
        app.state.owns_store = False
    settings = load_settings()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "model": settings.model}

    @app.post("/api/sessions")
    async def create_session() -> dict[str, str]:
        session_id = app.state.orch.new_session()
        return {"session_id": session_id}

    @app.post("/api/chat", response_model=TurnResponse)
    async def chat(body: ChatRequest) -> TurnResponse:
        o: Orchestrator = app.state.orch
        session_id = body.session_id or o.new_session()
        # Sync call: SQLite connection is bound to the server thread.
        result = o.handle_user_message(session_id, body.message)
        return _to_response(session_id, result)

    @app.post("/api/confirm", response_model=TurnResponse)
    async def confirm(body: ConfirmRequest) -> TurnResponse:
        o: Orchestrator = app.state.orch
        token = body.token
        if not token:
            pending = o.store.get_pending(body.session_id)
            if pending is None:
                raise HTTPException(status_code=400, detail="No pending confirmation")
            token = pending.token
        result = o.resolve_confirm(body.session_id, token, body.approved)
        return _to_response(body.session_id, result)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "argus.api:app",
        host="127.0.0.1",
        port=8787,
        reload=False,
    )


if __name__ == "__main__":
    main()
