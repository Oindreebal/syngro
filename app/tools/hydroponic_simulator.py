"""
tools/hydroponic_simulator.py
------------------------------
A fake (simulated) hydroponics rig. No real hardware is touched anywhere in
this project. This class is the ONLY place where "actions" actually change
system state, and it only exposes a small allowlisted set of methods --
there is no generic "run this command" method, so even if something
upstream misbehaved, there's no execution surface for arbitrary commands.

Why a simulator instead of real hardware?
- The assignment must be runnable by anyone with just Python + deps.
- It keeps the security story clean: the executor is a small, auditable
  Python class, not a serial/GPIO integration with real-world side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class SimulatorState:
    temperature: float = 24.0
    humidity: float = 60.0
    ph: float = 6.2
    ec: float = 1.8
    water_level: float = 70.0
    light_intensity: float = 400.0
    pump_on: bool = False
    fan_on: bool = False
    light_on: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HydroponicSimulator:
    """
    Exposes only a fixed, allowlisted set of action methods. Each method
    validates its own basic parameter shape defensively, but the REAL
    security boundary is action_guardrail.py, which runs before any of
    these methods are ever called.
    """

    def __init__(self) -> None:
        self.state = SimulatorState()
        self.action_log: list = []

    # --- allowlisted actions -------------------------------------------------

    def pump_on(self, duration_seconds: int) -> Dict[str, Any]:
        self.state.pump_on = True
        # Simulate effect: running the pump nudges water level and EC toward
        # circulation targets. This is a simplified illustrative model only.
        self.state.water_level = min(100.0, self.state.water_level + duration_seconds * 0.02)
        self.state.pump_on = False  # simulated: pump completes and turns off
        return self._record("pump_on", {"duration_seconds": duration_seconds})

    def pump_off(self) -> Dict[str, Any]:
        self.state.pump_on = False
        return self._record("pump_off", {})

    def fan_on(self, duration_seconds: int) -> Dict[str, Any]:
        self.state.fan_on = True
        self.state.temperature = max(15.0, self.state.temperature - duration_seconds * 0.005)
        self.state.fan_on = False
        return self._record("fan_on", {"duration_seconds": duration_seconds})

    def fan_off(self) -> Dict[str, Any]:
        self.state.fan_on = False
        return self._record("fan_off", {})

    def light_on(self, duration_seconds: int) -> Dict[str, Any]:
        self.state.light_on = True
        self.state.light_intensity = min(1000.0, self.state.light_intensity + 5)
        self.state.light_on = False
        return self._record("light_on", {"duration_seconds": duration_seconds})

    def light_off(self) -> Dict[str, Any]:
        self.state.light_on = False
        return self._record("light_off", {})

    def nutrient_dosing(self, amount_ml: float) -> Dict[str, Any]:
        self.state.ec = min(3.0, self.state.ec + amount_ml * 0.01)
        return self._record("nutrient_dosing", {"amount_ml": amount_ml})

    def water_refill(self, duration_seconds: int) -> Dict[str, Any]:
        self.state.water_level = min(100.0, self.state.water_level + duration_seconds * 0.05)
        return self._record("water_refill", {"duration_seconds": duration_seconds})

    def alert_user(self, reason: str = "") -> Dict[str, Any]:
        """A no-hardware-effect action: just surfaces a message to the user."""
        return self._record("alert_user", {"reason": reason})

    # --- internal helpers -----------------------------------------------------

    def _record(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        entry = {"action": action, "params": params, "resulting_state": self.state.to_dict()}
        self.action_log.append(entry)
        return entry
