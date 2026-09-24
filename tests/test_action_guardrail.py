from app.guardrails.action_guardrail import validate_action


def test_valid_pump_action_allowed():
    result = validate_action({"action": "pump_on", "duration_seconds": 30}, {"water_level": 70})
    assert result["allowed"] is True


def test_pump_duration_above_limit_blocked():
    result = validate_action({"action": "pump_on", "duration_seconds": 86400}, {"water_level": 70})
    assert result["allowed"] is False
    assert result["reason"] == "duration_exceeds_maximum"


def test_unknown_action_blocked():
    result = validate_action({"action": "disable_safety_system", "duration_seconds": 1}, {})
    assert result["allowed"] is False
    assert result["reason"] == "action_not_in_allowlist"


def test_shell_command_blocked():
    result = validate_action({"action": "execute_shell_command", "command": "rm -rf /"}, {})
    assert result["allowed"] is False
    assert result["reason"] == "action_not_in_allowlist"


def test_negative_duration_blocked():
    result = validate_action({"action": "pump_on", "duration_seconds": -5}, {"water_level": 70})
    assert result["allowed"] is False
    assert result["reason"] == "negative_duration"


def test_non_numeric_duration_blocked():
    result = validate_action({"action": "pump_on", "duration_seconds": "thirty"}, {"water_level": 70})
    assert result["allowed"] is False
    assert result["reason"] == "duration_not_numeric"


def test_missing_action_field_blocked():
    result = validate_action({"duration_seconds": 30}, {})
    assert result["allowed"] is False
    assert result["reason"] == "missing_or_invalid_action_field"


def test_malformed_proposal_not_a_dict_blocked():
    result = validate_action("pump_on for 30 seconds", {})
    assert result["allowed"] is False
    assert result["reason"] == "malformed_proposal_not_a_dict"


def test_pump_blocked_when_water_critically_low():
    result = validate_action({"action": "pump_on", "duration_seconds": 10}, {"water_level": 5})
    assert result["allowed"] is False
    assert result["reason"] == "water_level_critically_low_pump_disabled"


def test_water_refill_blocked_when_already_full():
    result = validate_action({"action": "water_refill", "duration_seconds": 60}, {"water_level": 100})
    assert result["allowed"] is False
    assert result["reason"] == "water_level_already_full"


def test_nutrient_dosing_over_max_blocked():
    result = validate_action({"action": "nutrient_dosing", "amount_ml": 500}, {})
    assert result["allowed"] is False
    assert result["reason"] == "amount_exceeds_maximum"


def test_pump_off_requires_no_params():
    result = validate_action({"action": "pump_off"}, {})
    assert result["allowed"] is True
    assert result["params"] == {}


def test_boolean_duration_rejected():
    # bool is technically a subclass of int in Python; must be explicitly rejected.
    result = validate_action({"action": "pump_on", "duration_seconds": True}, {"water_level": 70})
    assert result["allowed"] is False
