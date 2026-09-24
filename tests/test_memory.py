import tempfile
from pathlib import Path

from app.memory import MemoryStore


def _temp_store() -> MemoryStore:
    tmp_dir = tempfile.mkdtemp()
    return MemoryStore(db_path=Path(tmp_dir) / "test_hydroguard.db")


def test_add_and_retrieve_event():
    store = _temp_store()
    store.add_event("sensor_reading", {"ph": 6.1})
    events = store.get_recent_events(limit=5)
    assert len(events) == 1
    assert events[0]["event_type"] == "sensor_reading"
    assert events[0]["payload"]["ph"] == 6.1


def test_recent_events_limit_respected():
    store = _temp_store()
    for i in range(10):
        store.add_event("sensor_reading", {"ph": i})
    events = store.get_recent_events(limit=3)
    assert len(events) == 3
    # newest first
    assert events[0]["payload"]["ph"] == 9


def test_filter_by_event_type():
    store = _temp_store()
    store.add_event("sensor_reading", {"ph": 6.0})
    store.add_event("blocked_action", {"action": "pump_on"})
    events = store.get_recent_events(event_type="blocked_action", limit=5)
    assert len(events) == 1
    assert events[0]["event_type"] == "blocked_action"


def test_summarize_older_events():
    store = _temp_store()
    for i in range(25):
        store.add_event("sensor_reading", {"ph": i})
    summary = store.summarize_older_events(keep_recent=20)
    assert summary.get("older_events_summarized") == 5
