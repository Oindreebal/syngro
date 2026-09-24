"""
state.py
--------
Holds the CURRENT snapshot of the hydroponic system: the latest sensor
readings and a few derived fields. This is intentionally separate from
memory.py (which stores HISTORY). State answers "what is true right now?";
Memory answers "what happened recently?".

Why a separate module?
A beginner-friendly, explicit split makes it easy to explain in a viva:
- StateManager: current truth, used to validate actions safely
  (e.g. "is the water level currently too low to run the pump?").
- MemoryStore: append-only history, used for context and auditing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (easy to log/sort)."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SensorReading:
    """A single structured sensor snapshot."""

    ph: Optional[float] = None
    ec: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    water_level: Optional[float] = None
    light_intensity: Optional[float] = None
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StateManager:
    """
    Keeps the single "current" view of the hydroponic system.

    This is a plain in-memory object (backed optionally by the MemoryStore
    for persistence). Deliberately simple: a dict-like container with a
    couple of helper methods, not a database ORM.
    """

    def __init__(self, initial: Optional[SensorReading] = None) -> None:
        self._current: SensorReading = initial or SensorReading(
            ph=6.0,
            ec=1.6,
            temperature=24.0,
            humidity=60.0,
            water_level=70.0,
            light_intensity=400.0,
        )

    @property
    def current(self) -> SensorReading:
        return self._current

    def update_sensors(self, **kwargs: Any) -> SensorReading:
        """Update one or more sensor fields and refresh the timestamp."""
        data = self._current.to_dict()
        for key, value in kwargs.items():
            if key in data and value is not None:
                data[key] = value
        data["timestamp"] = utc_now_iso()
        self._current = SensorReading(**data)
        return self._current

    def as_dict(self) -> Dict[str, Any]:
        return self._current.to_dict()
