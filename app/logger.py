"""
logger.py
---------
Structured JSONL (JSON-lines) logging: one JSON object per line, written to
logs/hydroguard.log.jsonl. Every guardrail decision, agent action, and
system event goes through here.

Why JSONL instead of plain text logs?
Each line is independently parseable JSON, so during the presentation you
can literally `cat logs/hydroguard.log.jsonl | python -m json.tool` or grep
for `"result": "BLOCKED"` and get something a script (or a human) can read
easily, while still being human-readable line by line.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "hydroguard.log.jsonl"

LOG_DIR.mkdir(parents=True, exist_ok=True)

# Standard Python logging also prints to console for live demo visibility.
_console_logger = logging.getLogger("hydroguard")
if not _console_logger.handlers:
    _console_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    _console_logger.addHandler(handler)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(
    component: str,
    event: str,
    result: Optional[str] = None,
    reason: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Write one structured log record and echo a short line to the console.

    component: which part of the system logged this (e.g. "INPUT_GUARDRAIL")
    event: short description (e.g. "malicious_input_detected")
    result: e.g. "ALLOWED", "BLOCKED", "EXECUTED", "ERROR"
    reason: human-readable reason, especially for blocks
    details: any extra structured data (input text, action params, etc.)
    """
    record = {
        "timestamp": _utc_now_iso(),
        "component": component,
        "event": event,
        "result": result,
        "reason": reason,
        "details": details or {},
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    summary = f"{component} | {event} | result={result} | reason={reason}"
    if result == "BLOCKED":
        _console_logger.warning(summary)
    elif result == "ERROR":
        _console_logger.error(summary)
    else:
        _console_logger.info(summary)

    return record


def read_recent_logs(limit: int = 20) -> list:
    """Read the last `limit` log lines (for demos / debugging)."""
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines[-limit:]]
