from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from argus.api import create_app
from argus.orchestrator.loop import TurnResult


@dataclass
class FakeStore:
    _pending: Any = None

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
        if "open" in text.lower():
            return TurnResult(
                status="awaiting_confirm",
                reply="Confirm open_application?",
                confirm_token="tok123",
                pending_tool="open_application",
                pending_args={"app": "notepad"},
            )
        return TurnResult(status="completed", reply=f"echo:{text}")

    def resolve_confirm(self, session_id: str, token: str, approved: bool) -> TurnResult:
        return TurnResult(
            status="completed",
            reply="approved" if approved else "denied",
        )


def test_health_and_session():
    with TestClient(create_app(orch=FakeOrch())) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        sess = client.post("/api/sessions")
        assert sess.status_code == 200
        assert sess.json()["session_id"].startswith("sess_")


def test_chat_and_confirm_flow():
    with TestClient(create_app(orch=FakeOrch())) as client:
        chat = client.post("/api/chat", json={"message": "hello"})
        assert chat.status_code == 200
        body = chat.json()
        assert body["status"] == "completed"
        assert body["reply"] == "echo:hello"
        assert body["session_id"]

        pending = client.post(
            "/api/chat",
            json={"session_id": body["session_id"], "message": "Open notepad"},
        ).json()
        assert pending["status"] == "awaiting_confirm"
        assert pending["confirm_token"] == "tok123"

        done = client.post(
            "/api/confirm",
            json={
                "session_id": body["session_id"],
                "approved": True,
                "token": pending["confirm_token"],
            },
        ).json()
        assert done["status"] == "completed"
        assert done["reply"] == "approved"


def test_index_served():
    with TestClient(create_app(orch=FakeOrch())) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Argus" in page.text
