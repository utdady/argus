from __future__ import annotations

import hashlib
import json
import re
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


_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "it",
        "they",
        "them",
        "their",
        "this",
        "that",
        "these",
        "those",
        "do",
        "does",
        "did",
        "doing",
        "have",
        "has",
        "had",
        "having",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "from",
        "with",
        "about",
        "into",
        "over",
        "after",
        "and",
        "or",
        "but",
        "if",
        "as",
        "by",
        "what",
        "where",
        "when",
        "who",
        "whom",
        "which",
        "why",
        "how",
        "can",
        "could",
        "would",
        "should",
        "please",
        "tell",
        "find",
        "show",
        "get",
        "any",
        "anything",
        "notes",
        "note",
        "memory",
        "remember",
        "recall",
        "search",
    }
)


def build_fts_query(query: str) -> str | None:
    """Tokenize a natural-language query into an FTS5 OR expression."""
    tokens = re.findall(r"[a-z0-9]+", query.lower().replace("-", " "))
    terms: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if tok in _STOPWORDS or len(tok) < 2:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        terms.append(tok)
    if not terms:
        return None
    return " OR ".join(terms)


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
                tool_calls_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('user', 'tool')),
                created_at TEXT NOT NULL
            );

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

            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "tool_calls_json" not in cols:
            self._conn.execute(
                "ALTER TABLE messages ADD COLUMN tool_calls_json TEXT"
            )

        self._ensure_notes_fts()
        self._conn.commit()

    def _ensure_notes_fts(self) -> None:
        row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'fts_tokenizer'"
        ).fetchone()
        if row and row[0] == "porter":
            # Still ensure table exists for brand-new DBs that set meta incorrectly.
            exists = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='notes_fts'"
            ).fetchone()
            if exists:
                return

        self._conn.executescript(
            """
            DROP TRIGGER IF EXISTS notes_ai;
            DROP TRIGGER IF EXISTS notes_ad;
            DROP TRIGGER IF EXISTS notes_au;
            DROP TABLE IF EXISTS notes_fts;

            CREATE VIRTUAL TABLE notes_fts USING fts5(
                content,
                content='notes',
                content_rowid='id',
                tokenize='porter unicode61'
            );

            CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
                INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
            END;
            CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, content)
                VALUES('delete', old.id, old.content);
            END;
            CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, content)
                VALUES('delete', old.id, old.content);
                INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
            END;
            """
        )
        self._conn.execute(
            "INSERT INTO notes_fts(rowid, content) SELECT id, content FROM notes"
        )
        self._conn.execute(
            """
            INSERT INTO schema_meta(key, value) VALUES ('fts_tokenizer', 'porter')
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )

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
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        tool_calls_json = (
            json.dumps(tool_calls, sort_keys=True) if tool_calls else None
        )
        self._conn.execute(
            """
            INSERT INTO messages
            (session_id, role, content, tool_call_id, tool_calls_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, content, tool_call_id, tool_calls_json, _utc_now()),
        )
        self._conn.commit()

    def list_messages(self, session_id: str, limit: int = 40) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT role, content, tool_call_id, tool_calls_json FROM messages
            WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [self._row_to_message(r) for r in reversed(rows)]

    @staticmethod
    def _row_to_message(r: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        item = dict(r)
        raw = item.pop("tool_calls_json", None)
        item["tool_calls"] = json.loads(raw) if raw else []
        return item

    def load_history(
        self, session_id: str, max_user_turns: int = 12, fetch_cap: int = 200
    ) -> list[dict[str, Any]]:
        """Return recent messages starting at a user-turn boundary.

        Row-limited windows can start mid-turn (e.g. orphan tool results).
        This keeps whole turns: from the Nth-last user message forward.
        """
        if max_user_turns <= 0:
            return []
        rows = self._conn.execute(
            """
            SELECT role, content, tool_call_id, tool_calls_json FROM messages
            WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, fetch_cap),
        ).fetchall()
        chron = [self._row_to_message(r) for r in reversed(rows)]
        user_idxs = [i for i, m in enumerate(chron) if m["role"] == "user"]
        if not user_idxs:
            return chron
        start = user_idxs[-max_user_turns] if len(user_idxs) >= max_user_turns else user_idxs[0]
        return chron[start:]

    def add_note(self, content: str, user_id: str, source: str = "user") -> int:
        cur = self._conn.execute(
            "INSERT INTO notes (user_id, content, source, created_at) VALUES (?, ?, ?, ?)",
            (user_id, content, source, _utc_now()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def clear_notes(self, user_id: str | None = None) -> None:
        if user_id is None:
            self._conn.execute("DELETE FROM notes")
        else:
            self._conn.execute("DELETE FROM notes WHERE user_id = ?", (user_id,))
        self._conn.commit()

    def search_notes(self, query: str, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        fts = build_fts_query(query)
        if fts:
            try:
                rows = self._conn.execute(
                    """
                    SELECT n.id, n.content, n.source, n.created_at
                    FROM notes_fts f
                    JOIN notes n ON n.id = f.rowid
                    WHERE notes_fts MATCH ? AND n.user_id = ?
                    ORDER BY rank, n.id DESC
                    LIMIT ?
                    """,
                    (fts, user_id, limit),
                ).fetchall()
                if rows:
                    return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                pass

        # LIKE fallback: any token substring match
        tokens = re.findall(r"[a-z0-9]+", query.lower().replace("-", " "))
        terms = [t for t in tokens if t not in _STOPWORDS and len(t) >= 2]
        if not terms:
            terms = [query.strip()] if query.strip() else []
        if not terms:
            return []

        clauses = " OR ".join(["content LIKE ?" for _ in terms])
        params: list[Any] = [user_id, *[f"%{t}%" for t in terms], limit]
        rows = self._conn.execute(
            f"""
            SELECT id, content, source, created_at FROM notes
            WHERE user_id = ? AND ({clauses})
            ORDER BY id DESC LIMIT ?
            """,
            params,
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
