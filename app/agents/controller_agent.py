"""
agents/controller_agent.py
-----------------------------
Combines outputs from other agents (vision + sensor + recent memory + the
user's own request) into a compact context, and asks the LLM to PROPOSE a
single structured action.

CRITICAL: this module returns a proposal dict. It has NO access to the
simulator and cannot execute anything. The proposal must be passed to
guardrails.action_guardrail.validate_action() by the caller (main.py)
before anything happens. This physical separation -- the controller agent
literally does not import hydroponic_simulator -- is what makes the "LLM
never directly controls the actuator" guarantee real rather than just a
comment.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.llm.client import propose_action
from app.logger import log_event


def run_controller_agent(
    user_request: str,
    sensor_result: Optional[Dict[str, Any]] = None,
    vision_result: Optional[Dict[str, Any]] = None,
    recent_events: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build a compact context and ask the LLM to propose ONE structured action.
    Returns the raw proposal dict, e.g.:
        {"action": "pump_on", "duration_seconds": 30, "reason": "..."}
    This is UNVALIDATED -- treat it as untrusted until action_guardrail
    approves it.
    """
    context = {
        "user_request": user_request,
        "sensor_summary": sensor_result.get("summary") if sensor_result else None,
        "compact_sensor_state": sensor_result.get("compact_state") if sensor_result else None,
        "vision_observations": vision_result.get("visible_observations") if vision_result else None,
        "vision_stress_level": vision_result.get("stress_level") if vision_result else None,
        # Only a handful of recent events are included -- NOT the entire
        # history -- this is the "compact context" long-context strategy.
        "recent_events": (recent_events or [])[:5],
    }

    proposal = propose_action(context)

    log_event(
        component="CONTROLLER_AGENT",
        event="propose_action",
        result="PROPOSED",
        details={"context": context, "proposal": proposal},
    )
    return proposal
