"""
guardrails/action_guardrail.py
--------------------------------
Checkpoint #2, and the most important safety component in the whole
project: EVERY proposed action, from ANY agent, must pass through
`validate_action()` before the simulator is allowed to run it.

Core principle (see README section 3):

    LLM/Agent PROPOSES an action (a plain dict, not a function call).
    This module VALIDATES the proposal deterministically.
    Only if validation passes does the executor call the simulator.

This module never imports the LLM client and never calls it. Its
correctness must not depend on model behaviour -- that's the whole point.

Validation checks (in order, each producing an early BLOCK if it fails):
  1. Structural validity  - is the proposal shaped like {"action": str,
     "duration_seconds": number, ...}? Reject malformed / non-JSON-like
     input outright, fail-safe.
  2. Allowlist membership  - is `action` one of the explicitly permitted
     action names? Anything else (including things like
     "execute_shell_command" or "disable_safety_system") is blocked.
  3. Parameter validation  - correct type, non-negative, numeric (not a
     string, not NaN, not a list).
  4. Numeric limits        - duration/amount within a configured maximum
     for that specific action.
  5. Current-state safety  - does executing this conflict with the current
     simulated system state (e.g. don't refill water that's already full,
     don't run the pump if water level is critically low)?
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from app.logger import log_event

# The ONLY actions the system is allowed to ever execute.
ALLOWED_ACTIONS = {
    "pump_on",
    "pump_off",
    "fan_on",
    "fan_off",
    "light_on",
    "light_off",
    "nutrient_dosing",
    "water_refill",
    "alert_user",
}

# Example configurable maximums -- tune per real deployment.
MAX_DURATION_SECONDS = {
    "pump_on": 120,       # 2 minutes max per activation
    "fan_on": 3600,       # 1 hour max
    "light_on": 43200,    # 12 hours max (grow lights run long)
    "water_refill": 300,  # 5 minutes max
}
MAX_NUTRIENT_ML = 50.0

# Actions that take no duration/amount parameter at all.
NO_PARAM_ACTIONS = {"pump_off", "fan_off", "light_off"}


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):  # bool is a subclass of int -- explicitly reject
        return False
    if not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return False
    return True


def validate_action(
    proposal: Dict[str, Any], current_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate a proposed action dict. Returns:
        {"allowed": bool, "reason": str, "action": ..., "params": {...}}

    `current_state` is the simulator's current SimulatorState.to_dict() (or
    None if unavailable -- unavailability itself is handled fail-safe).
    """
    current_state = current_state or {}

    # --- 1. structural validity ------------------------------------------------
    if not isinstance(proposal, dict):
        return _blocked("malformed_proposal_not_a_dict", proposal)

    action = proposal.get("action")
    if not isinstance(action, str) or not action:
        return _blocked("missing_or_invalid_action_field", proposal)

    # --- 2. allowlist membership -------------------------------------------------
    if action not in ALLOWED_ACTIONS:
        return _blocked("action_not_in_allowlist", proposal, action=action)

    # --- 3 & 4. parameter validation + numeric limits ---------------------------
    if action == "alert_user":
        params = {"reason": proposal.get("reason", "")}
        return _allowed(action, params)

    if action in NO_PARAM_ACTIONS:
        return _allowed(action, {})

    if action == "nutrient_dosing":
        amount = proposal.get("amount_ml", proposal.get("duration_seconds"))
        if not _is_number(amount) or amount < 0:
            return _blocked("invalid_or_negative_amount", proposal, action=action)
        if amount > MAX_NUTRIENT_ML:
            return _blocked("amount_exceeds_maximum", proposal, action=action)
        return _allowed(action, {"amount_ml": amount})

    # Remaining allowlisted actions take duration_seconds: pump_on, fan_on,
    # light_on, water_refill.
    duration = proposal.get("duration_seconds")
    if not _is_number(duration):
        return _blocked("duration_not_numeric", proposal, action=action)
    if duration < 0:
        return _blocked("negative_duration", proposal, action=action)

    max_allowed = MAX_DURATION_SECONDS.get(action)
    if max_allowed is not None and duration > max_allowed:
        return _blocked("duration_exceeds_maximum", proposal, action=action)

    # --- 5. current-state safety checks -----------------------------------------
    water_level = current_state.get("water_level")
    if action == "pump_on" and water_level is not None and water_level < 10:
        return _blocked("water_level_critically_low_pump_disabled", proposal, action=action)

    if action == "water_refill" and water_level is not None and water_level >= 100:
        return _blocked("water_level_already_full", proposal, action=action)

    params = {"duration_seconds": duration}
    return _allowed(action, params)


def _allowed(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    result = {"allowed": True, "reason": "passed_all_checks", "action": action, "params": params}
    log_event(
        component="ACTION_GUARDRAIL",
        event="validate_action",
        result="ALLOWED",
        reason=result["reason"],
        details={"action": action, "params": params},
    )
    return result


def _blocked(reason: str, proposal: Any, action: Optional[str] = None) -> Dict[str, Any]:
    result = {"allowed": False, "reason": reason, "action": action, "params": {}}
    log_event(
        component="ACTION_GUARDRAIL",
        event="validate_action",
        result="BLOCKED",
        reason=reason,
        details={"raw_proposal": proposal if isinstance(proposal, (dict, str, int, float)) else str(proposal)},
    )
    return result
