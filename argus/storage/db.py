from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def confirm_token(session_id: str, tool_name: str, arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    raw = f"{session_id}|{tool_name}|{canonical}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@dataclass
class PendingConfirm:
    token: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    tool_call_id: str
    reason: str


class Storage:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                role TEXT NOT NULL,
                content TEXT,
                tool_call_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('user', 'tool')),
                created_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                content,
                content='notes',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
            END;
            CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, content)
                VALUES('delete', old.id, old.content);
            END;
            CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, content)
                VALUES('delete', old.id, old.content);
                INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
            END;

            CREATE TABLE IF NOT EXISTS tool_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                decision TEXT NOT NULL,
                outcome TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_confirmations (
                token TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                tool_call_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def create_session(self, session_id: str, user_id: str, device_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO sessions (id, user_id, device_id, created_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, device_id, _utc_now()),
        )
        self._conn.commit()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str | None,
        tool_call_id: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO messages (session_id, role, content, tool_call_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, tool_call_id, _utc_now()),
        )
        self._conn.commit()

    def list_messages(self, session_id: str, limit: int = 40) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT role, content, tool_call_id FROM messages
            WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def add_note(self, content: str, user_id: str, source: str = "user") -> int:
        cur = self._conn.execute(
            "INSERT INTO notes (user_id, content, source, created_at) VALUES (?, ?, ?, ?)",
            (user_id, content, source, _utc_now()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def search_notes(self, query: str, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        # FTS5 MATCH; fall back to LIKE if query is awkward for FTS
        try:
            rows = self._conn.execute(
                """
                SELECT n.id, n.content, n.source, n.created_at
                FROM notes_fts f
                JOIN notes n ON n.id = f.rowid
                WHERE notes_fts MATCH ? AND n.user_id = ?
                ORDER BY n.id DESC
                LIMIT ?
                """,
                (query, user_id, limit),
            ).fetchall()
            if rows:
                return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            pass
        like = f"%{query}%"
        rows = self._conn.execute(
            """
            SELECT id, content, source, created_at FROM notes
            WHERE user_id = ? AND content LIKE ?
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, like, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def audit(
        self,
        *,
        session_id: str,
        user_id: str,
        device_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        decision: str,
        outcome: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO tool_audit
            (session_id, user_id, device_id, tool_name, arguments_json, decision, outcome, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                device_id,
                tool_name,
                json.dumps(arguments, sort_keys=True),
                decision,
                outcome,
                _utc_now(),
            ),
        )
        self._conn.commit()

    def set_pending(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str,
        reason: str,
    ) -> str:
        token = confirm_token(session_id, tool_name, arguments)
        self.clear_pending(session_id)
        self._conn.execute(
            """
            INSERT INTO pending_confirmations
            (token, session_id, tool_name, arguments_json, tool_call_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                session_id,
                tool_name,
                json.dumps(arguments, sort_keys=True),
                tool_call_id,
                reason,
                _utc_now(),
            ),
        )
        self._conn.commit()
        return token

    def get_pending(self, session_id: str) -> PendingConfirm | None:
        row = self._conn.execute(
            """
            SELECT token, session_id, tool_name, arguments_json, tool_call_id, reason
            FROM pending_confirmations WHERE session_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        if not row:
            return None
        return PendingConfirm(
            token=row["token"],
            session_id=row["session_id"],
            tool_name=row["tool_name"],
            arguments=json.loads(row["arguments_json"]),
            tool_call_id=row["tool_call_id"],
            reason=row["reason"],
        )

    def get_pending_by_token(self, token: str) -> PendingConfirm | None:
        row = self._conn.execute(
            """
            SELECT token, session_id, tool_name, arguments_json, tool_call_id, reason
            FROM pending_confirmations WHERE token = ?
            """,
            (token,),
        ).fetchone()
        if not row:
            return None
        return PendingConfirm(
            token=row["token"],
            session_id=row["session_id"],
            tool_name=row["tool_name"],
            arguments=json.loads(row["arguments_json"]),
            tool_call_id=row["tool_call_id"],
            reason=row["reason"],
        )

    def clear_pending(self, session_id: str) -> None:
        self._conn.execute(
            "DELETE FROM pending_confirmations WHERE session_id = ?",
            (session_id,),
        )
        self._conn.commit()
