"""Tiny SQLite persistence layer. SQLite ships with Python, so there's nothing to install."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from .models import IncomingMessage, ProcessedMessage, Stats, Triage

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT    NOT NULL,
    message     TEXT    NOT NULL,   -- IncomingMessage as JSON
    triage      TEXT    NOT NULL,   -- Triage as JSON
    category    TEXT    NOT NULL,   -- duplicated for fast filtering
    urgency     TEXT    NOT NULL,
    needs_human INTEGER NOT NULL,
    engine      TEXT    NOT NULL,
    notified    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_messages_category ON messages(category);
"""


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def add(self, msg: IncomingMessage, triage: Triage, engine: str) -> ProcessedMessage:
        now = datetime.now(UTC)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO messages (received_at, message, triage, category, urgency, needs_human, engine)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now.isoformat(), msg.model_dump_json(), triage.model_dump_json(),
                 triage.category.value, triage.urgency.value, int(triage.needs_human), engine),
            )
        return ProcessedMessage(id=cur.lastrowid, received_at=now, message=msg, triage=triage,
                                engine=engine)

    def mark_notified(self, message_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE messages SET notified = 1 WHERE id = ?", (message_id,))

    def get(self, message_id: int) -> ProcessedMessage | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return _row(row) if row else None

    def list(self, category: str | None = None, limit: int = 50) -> list[ProcessedMessage]:
        sql, args = "SELECT * FROM messages", []
        if category:
            sql += " WHERE category = ?"
            args.append(category)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [_row(r) for r in rows]

    def stats(self) -> Stats:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            cats = self._conn.execute("SELECT category, COUNT(*) FROM messages GROUP BY category").fetchall()
            urg = self._conn.execute("SELECT urgency, COUNT(*) FROM messages GROUP BY urgency").fetchall()
            human = self._conn.execute("SELECT COUNT(*) FROM messages WHERE needs_human = 1").fetchone()[0]
        return Stats(total=total, by_category={r[0]: r[1] for r in cats},
                     by_urgency={r[0]: r[1] for r in urg}, needs_human=human)


def _row(row: sqlite3.Row) -> ProcessedMessage:
    return ProcessedMessage(
        id=row["id"],
        received_at=datetime.fromisoformat(row["received_at"]),
        message=IncomingMessage.model_validate(json.loads(row["message"])),
        triage=Triage.model_validate(json.loads(row["triage"])),
        engine=row["engine"],
        notified=bool(row["notified"]),
    )
