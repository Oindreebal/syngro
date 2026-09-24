"""
agents/sensor_agent.py
------------------------
Interprets structured sensor data with plain, deterministic Python logic --
no LLM required. This is a legitimate "agent" in the multi-agent sense (a
specialized component with a defined job and structured input/output), it
just happens not to need a model to do its job well and predictably.

It reuses the Drosophila-inspired preprocessor to turn raw numbers into a
compact categorical state, then adds a short human-readable summary.

IMPORTANT: thresholds are example operational values, not universal
biological truths -- see README "limitations".
"""

from __future__ import annotations

from typing import Any, Dict

from app.logger import log_event
from app.preprocessing.drosophila_preprocessor import DrosophilaPreprocessor


def run_sensor_agent(raw_sensors: Dict[str, Any], preprocessor: DrosophilaPreprocessor) -> Dict[str, Any]:
    """
    Input: raw sensor dict, e.g. {"ph": 6.9, "ec": 2.6, "temperature": 31.0, ...}
    Output: compact state + a short summary, e.g.
        {
          "compact_state": {...from preprocessor...},
          "summary": "Temperature HIGH, EC HIGH -> overall STRESS"
        }
    """
    compact_state = preprocessor.process(raw_sensors)

    abnormal_fields = [
        key.replace("_state", "")
        for key, value in compact_state.items()
        if key.endswith("_state") and value in ("LOW", "HIGH")
    ]

    if abnormal_fields:
        details = ", ".join(
            f"{field} {compact_state[f'{field}_state']}" for field in abnormal_fields
        )
        summary = f"{details} -> overall {compact_state['overall_state']}"
    else:
        summary = f"All monitored readings NORMAL -> overall {compact_state['overall_state']}"

    result = {"compact_state": compact_state, "summary": summary, "raw_sensors": raw_sensors}

    log_event(component="SENSOR_AGENT", event="interpret_sensors", result="OK", details=result)
    return result
