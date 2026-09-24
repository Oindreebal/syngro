"""
memory.py
---------
Simple persistent HISTORY store, implemented with SQLite (part of the
Python standard library — no extra dependency, one file on disk, and easy
to open with any SQLite browser during a viva to literally show the data).

Why SQLite instead of plain JSON?
- Structured querying ("give me the last 5 sensor readings") without
  writing custom JSON-parsing code.
- Safe concurrent writes (multiple agents can log events).
- Still a single file (hydroguard.db) -- no server to run, easy to explain.

Why NOT a vector database / long-context LLM memory?
The assignment only requires remembering structured recent events
(readings, observations, actions). A vector DB would add complexity
without adding value here. See docs/LEARNING_GUIDE.md, section on
"long-context handling", for the fuller justification.

This module implements the "retain recent, summarize/limit older" strategy:
`get_recent_events()` returns only the most recent N rows instead of the
entire history, which is what gets passed to the controller agent as
compact context.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "logs" / "hydroguard.db"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """Append-only event history backed by SQLite."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,      -- e.g. sensor_reading, image_observation,
                                                    -- proposed_action, executed_action, blocked_action, user_request
                    payload TEXT NOT NULL           -- JSON-encoded details
                )
                """
            )
            conn.commit()

    def add_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Append one structured event to history."""
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO events (timestamp, event_type, payload) VALUES (?, ?, ?)",
                (_utc_now_iso(), event_type, json.dumps(payload)),
            )
            conn.commit()

    def get_recent_events(
        self, event_type: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Return the most recent `limit` events (optionally filtered by type),
        newest first. This is the "compact context" the controller agent
        receives instead of the entire history -- see LEARNING_GUIDE.md.
        """
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            if event_type:
                cursor = conn.execute(
                    "SELECT * FROM events WHERE event_type = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (event_type, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
                )
            rows = cursor.fetchall()

        events = []
        for row in rows:
            events.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "payload": json.loads(row["payload"]),
                }
            )
        return events

    def summarize_older_events(self, keep_recent: int = 20) -> Dict[str, int]:
        """
        Very simple "summarization" strategy: count how many events of each
        type exist beyond the most recent `keep_recent`. In a bigger system
        this could produce an LLM-written text summary; here a count is
        enough to demonstrate the *concept* of not re-sending raw history.
        """
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
            if total <= keep_recent:
                return {}
            older_count = total - keep_recent
            return {"older_events_summarized": older_count}
