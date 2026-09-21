from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from argus.config import load_settings
from argus.factory import build_orchestrator, build_voice
from argus.orchestrator.loop import Orchestrator, TurnResult
from argus.providers.base import SpeechToText, TextToSpeech
from argus.providers.null_voice import NullSTT, NullTTS

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


class VoiceResponse(TurnResponse):
    transcript: str
    audio_base64: str | None = None
    audio_mime: str | None = None
    voice_enabled: bool = False


def _to_response(session_id: str, result: TurnResult) -> TurnResponse:
    return TurnResponse(
        session_id=session_id,
        status=result.status,
        reply=result.reply,
        confirm_token=result.confirm_token,
        pending_tool=result.pending_tool,
        pending_args=result.pending_args,
    )


def create_app(
    orch: Orchestrator | None = None,
    *,
    stt: SpeechToText | None = None,
    tts: TextToSpeech | None = None,
    voice_enabled: bool | None = None,
) -> FastAPI:
    """Build the FastAPI app. Pass orch/stt/tts in tests to avoid live models."""
    injected = orch
    settings = load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if injected is not None:
            app.state.orch = injected
            app.state.owns_store = False
        else:
            built, _store = build_orchestrator(settings)
            app.state.orch = built
            app.state.owns_store = True

        if stt is not None and tts is not None:
            app.state.stt = stt
            app.state.tts = tts
            app.state.voice_enabled = (
                bool(voice_enabled) if voice_enabled is not None else True
            )
        else:
            built_stt, built_tts, enabled = build_voice(settings)
            app.state.stt = built_stt
            app.state.tts = built_tts
            app.state.voice_enabled = enabled

        yield
        if getattr(app.state, "owns_store", False):
            app.state.orch.store.close()

    app = FastAPI(title="Argus", version="0.1.0", lifespan=lifespan)
    if injected is not None:
        app.state.orch = injected
        app.state.owns_store = False
    app.state.stt = stt if stt is not None else NullSTT()
    app.state.tts = tts if tts is not None else NullTTS()
    app.state.voice_enabled = (
        bool(voice_enabled)
        if voice_enabled is not None
        else (stt is not None and tts is not None)
    )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "model": settings.model,
            "voice_enabled": bool(getattr(app.state, "voice_enabled", False)),
        }

    @app.post("/api/sessions")
    async def create_session() -> dict[str, str]:
        session_id = app.state.orch.new_session()
        return {"session_id": session_id}

    @app.post("/api/chat", response_model=TurnResponse)
    async def chat(body: ChatRequest) -> TurnResponse:
        o: Orchestrator = app.state.orch
        session_id = body.session_id or o.new_session()
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

    @app.post("/api/voice", response_model=VoiceResponse)
    async def voice(
        audio: UploadFile = File(...),
        session_id: str | None = Form(default=None),
    ) -> VoiceResponse:
        if not getattr(app.state, "voice_enabled", False):
            raise HTTPException(
                status_code=503,
                detail='Voice disabled. Set ARGUS_VOICE_ENABLED=1 and pip install -e ".[voice]"',
            )
        raw = await audio.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty audio upload")
        mime = audio.content_type or "audio/wav"
        try:
            transcript = app.state.stt.transcribe(raw, mime_type=mime).strip()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"STT failed: {exc}") from exc
        if not transcript:
            raise HTTPException(status_code=400, detail="Could not transcribe audio")

        o: Orchestrator = app.state.orch
        sid = session_id or o.new_session()
        result = o.handle_user_message(sid, transcript)
        audio_b64 = None
        audio_mime = None
        if result.status == "completed" and result.reply:
            try:
                wav, audio_mime = app.state.tts.synthesize(result.reply)
                if wav:
                    audio_b64 = base64.b64encode(wav).decode("ascii")
            except Exception as exc:  # noqa: BLE001
                # Text reply still succeeds if TTS fails.
                audio_b64 = None
                audio_mime = f"error:{exc}"

        return VoiceResponse(
            session_id=sid,
            status=result.status,
            reply=result.reply,
            confirm_token=result.confirm_token,
            pending_tool=result.pending_tool,
            pending_args=result.pending_args,
            transcript=transcript,
            audio_base64=audio_b64,
            audio_mime=audio_mime if audio_b64 else None,
            voice_enabled=True,
        )

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
