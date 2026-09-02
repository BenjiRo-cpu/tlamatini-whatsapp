from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    """Persistencia pequeña y suficiente para un piloto o demostración."""

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_state (
                    user_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_user
                    ON conversation_messages(user_id, id DESC);
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    correct INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms REAL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    def claim_message(self, message_id: str) -> bool:
        """Reserva un mensaje. Los fallidos se pueden reintentar; los demás no."""
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT status,received_at FROM processed_messages WHERE message_id = ?", (message_id,)
            ).fetchone()
            if row and row["status"] != "failed":
                stale = (
                    row["status"] == "processing"
                    and datetime.fromisoformat(row["received_at"]) < datetime.now(timezone.utc) - timedelta(minutes=5)
                )
                if not stale:
                    return False
            if row:
                db.execute(
                    "UPDATE processed_messages SET status='processing', received_at=?, completed_at=NULL, error=NULL WHERE message_id=?",
                    (_now(), message_id),
                )
            else:
                db.execute(
                    "INSERT INTO processed_messages(message_id,status,received_at) VALUES (?, 'processing', ?)",
                    (message_id, _now()),
                )
            return True

    def complete_message(self, message_id: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE processed_messages SET status='completed', completed_at=? WHERE message_id=?",
                (_now(), message_id),
            )

    def fail_message(self, message_id: str, error: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE processed_messages SET status='failed', completed_at=?, error=? WHERE message_id=?",
                (_now(), error[:500], message_id),
            )

    def append_message(self, user_id: str, role: str, content: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO conversation_messages(user_id,role,content,created_at) VALUES (?,?,?,?)",
                (user_id, role, content, _now()),
            )

    def recent_messages(self, user_id: str, limit: int = 8) -> list[dict[str, str]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT role,content FROM conversation_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_state(self, user_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT state_json FROM conversation_state WHERE user_id=?", (user_id,)
            ).fetchone()
        return json.loads(row["state_json"]) if row else {}

    def update_state(self, user_id: str, **updates: Any) -> dict[str, Any]:
        state = self.get_state(user_id)
        state.update(updates)
        with self._lock, self._connect() as db:
            db.execute(
                """INSERT INTO conversation_state(user_id,state_json,updated_at) VALUES (?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at""",
                (user_id, json.dumps(state, ensure_ascii=False), _now()),
            )
        return state

    def clear_state(self, user_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM conversation_state WHERE user_id=?", (user_id,))

    def save_quiz_result(self, user_id: str, topic: str, correct: int, total: int) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO quiz_results(user_id,topic,correct,total,created_at) VALUES (?,?,?,?,?)",
                (user_id, topic, correct, total, _now()),
            )

    def quiz_progress(self, user_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(correct),0) AS correct, COALESCE(SUM(total),0) AS total FROM quiz_results WHERE user_id=?",
                (user_id,),
            ).fetchone()
        total = int(row["total"])
        correct = int(row["correct"])
        return {
            "preguntas_respondidas": total,
            "aciertos": correct,
            "porcentaje": round(correct * 100 / total, 1) if total else 0,
        }

    def record_metric(self, event: str, status: str, latency_ms: float | None = None, detail: str = "") -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO metrics(event,status,latency_ms,detail,created_at) VALUES (?,?,?,?,?)",
                (event, status, latency_ms, detail[:500], _now()),
            )

    def metrics_summary(self) -> dict[str, Any]:
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) AS n FROM metrics WHERE event='message'").fetchone()["n"]
            errors = db.execute("SELECT COUNT(*) AS n FROM metrics WHERE event='message' AND status='error'").fetchone()["n"]
            latency = db.execute("SELECT AVG(latency_ms) AS avg_ms FROM metrics WHERE event='message' AND latency_ms IS NOT NULL").fetchone()["avg_ms"]
            tools = db.execute("SELECT COUNT(*) AS n FROM metrics WHERE event='tool'").fetchone()["n"]
        return {
            "messages": total,
            "errors": errors,
            "error_rate": round(errors / total, 4) if total else 0,
            "average_latency_ms": round(latency or 0, 2),
            "tool_calls": tools,
        }
