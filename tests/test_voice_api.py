from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from argus.api import create_app
from argus.orchestrator.loop import TurnResult


@dataclass
class FakeStore:
    _pending: object | None = None

    def get_pending(self, session_id: str):
        return self._pending

    def close(self) -> None:
        return None


class FakeOrch:
    def __init__(self) -> None:
        self.store = FakeStore()
        self._n = 0

    def new_session(self) -> str:
        self._n += 1
        return f"sess_{self._n}"

    def handle_user_message(self, session_id: str, text: str) -> TurnResult:
        return TurnResult(status="completed", reply=f"heard:{text}")


class FakeSTT:
    def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> str:
        assert audio
        return "what time is it"


class FakeTTS:
    def synthesize(self, text: str) -> tuple[bytes, str]:
        return b"RIFF_FAKE_WAV", "audio/wav"


def test_voice_roundtrip():
    client = TestClient(
        create_app(
            orch=FakeOrch(),
            stt=FakeSTT(),
            tts=FakeTTS(),
            voice_enabled=True,
        )
    )
    with client:
        health = client.get("/api/health").json()
        assert health["voice_enabled"] is True

        res = client.post(
            "/api/voice",
            data={"session_id": "sess_1"},
            files={"audio": ("ptt.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["transcript"] == "what time is it"
        assert body["reply"] == "heard:what time is it"
        assert body["audio_base64"]
        assert body["audio_mime"] == "audio/wav"


def test_voice_disabled_returns_503():
    client = TestClient(
        create_app(
            orch=FakeOrch(),
            stt=FakeSTT(),
            tts=FakeTTS(),
            voice_enabled=False,
        )
    )
    with client:
        res = client.post(
            "/api/voice",
            files={"audio": ("ptt.webm", b"x", "audio/webm")},
        )
        assert res.status_code == 503
