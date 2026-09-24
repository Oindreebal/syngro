"""
main.py
-------
Orchestrates the full pipeline described in the README diagram:

  TEXT / IMAGE -> INPUT GUARDRAIL -> ROUTER -> AGENTS -> CONTROLLER
      -> PROPOSED ACTION -> ACTION GUARDRAIL -> ALLOW: SIMULATOR
                                              -> BLOCK: LOGGER

Run this file directly for an interactive demo, or import
`process_request()` from tests / other scripts.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

from app.agents.controller_agent import run_controller_agent
from app.agents.knowledge_agent import run_knowledge_agent
from app.agents.sensor_agent import run_sensor_agent
from app.agents.vision_agent import run_vision_agent
from app.guardrails.action_guardrail import validate_action
from app.guardrails.input_guardrail import check_text
from app.logger import log_event
from app.memory import MemoryStore
from app.preprocessing.drosophila_preprocessor import DrosophilaPreprocessor
from app.router import route
from app.state import StateManager
from app.tools.hydroponic_simulator import HydroponicSimulator

# Shared, process-wide instances (kept simple for a student project --
# no dependency-injection framework needed).
memory = MemoryStore()
state_manager = StateManager()
preprocessor = DrosophilaPreprocessor()
simulator = HydroponicSimulator()


def _load_image_base64(image_path: Optional[str]) -> Optional[str]:
    if not image_path:
        return None
    path = Path(image_path)
    if not path.exists():
        log_event(component="MAIN", event="load_image", result="ERROR", reason="file_not_found")
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def process_request(
    text: Optional[str] = None,
    image_path: Optional[str] = None,
    sensor_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run one full request through the pipeline and return a structured
    result dict describing what happened at every stage (useful both for
    the demo CLI and for automated tests).
    """
    pipeline_trace: Dict[str, Any] = {"input": {"text": text, "has_image": bool(image_path), "sensor_data": sensor_data}}

    # ---- STAGE 1: INPUT GUARDRAIL ------------------------------------------------
    if text:
        guard_result = check_text(text, source="user_text")
        pipeline_trace["input_guardrail"] = guard_result
        if not guard_result["allowed"]:
            memory.add_event("blocked_input", {"text": text, "reason": guard_result["reason"]})
            pipeline_trace["final_result"] = "BLOCKED_AT_INPUT_GUARDRAIL"
            return pipeline_trace
    else:
        pipeline_trace["input_guardrail"] = {"allowed": True, "reason": "no_text_input"}

    memory.add_event("user_request", {"text": text, "has_image": bool(image_path), "sensor_data": sensor_data})

    # ---- STAGE 2: ROUTER ----------------------------------------------------------
    image_base64 = _load_image_base64(image_path)
    chosen_agents = route(text=text, image_base64=image_base64, sensor_data=sensor_data)
    pipeline_trace["routed_to"] = chosen_agents

    # ---- STAGE 3: AGENTS ------------------------------------------------------------
    sensor_result = None
    vision_result = None

    if "sensor" in chosen_agents and sensor_data:
        sensor_result = run_sensor_agent(sensor_data, preprocessor)
        state_manager.update_sensors(**sensor_data)
        memory.add_event("sensor_reading", sensor_result)
        pipeline_trace["sensor_result"] = sensor_result

    if "vision" in chosen_agents:
        vision_result = run_vision_agent(image_base64, filename_hint=image_path or "")
        memory.add_event("image_observation", vision_result)
        pipeline_trace["vision_result"] = vision_result

        # Enforce: if the vision agent flagged untrusted text inside the
        # image and THAT text guardrail check blocked it, we stop here --
        # we never proceed to let it influence an action.
        image_guard = vision_result.get("image_text_guardrail")
        if image_guard and not image_guard.get("allowed", True):
            pipeline_trace["final_result"] = "BLOCKED_IMAGE_TEXT_INJECTION"
            return pipeline_trace

    if "knowledge" in chosen_agents and text:
        knowledge_result = run_knowledge_agent(text)
        pipeline_trace["knowledge_result"] = knowledge_result

    # ---- STAGE 4: CONTROLLER (only if an action was requested) --------------------
    if "controller" in chosen_agents and text:
        recent_events = memory.get_recent_events(limit=5)
        proposal = run_controller_agent(
            user_request=text,
            sensor_result=sensor_result,
            vision_result=vision_result,
            recent_events=recent_events,
        )
        pipeline_trace["proposed_action"] = proposal
        memory.add_event("proposed_action", proposal)

        # ---- STAGE 5: ACTION GUARDRAIL --------------------------------------------
        validation = validate_action(proposal, current_state=simulator.state.to_dict())
        pipeline_trace["action_guardrail"] = validation

        if validation["allowed"]:
            method = getattr(simulator, validation["action"])
            exec_result = method(**validation["params"])
            pipeline_trace["execution_result"] = exec_result
            memory.add_event("executed_action", {"action": validation["action"], "params": validation["params"]})
            pipeline_trace["final_result"] = "ACTION_EXECUTED"
        else:
            memory.add_event("blocked_action", {"proposal": proposal, "reason": validation["reason"]})
            pipeline_trace["final_result"] = "ACTION_BLOCKED"

    if "final_result" not in pipeline_trace:
        pipeline_trace["final_result"] = "RESPONDED_NO_ACTION"

    return pipeline_trace


def _print_trace(trace: Dict[str, Any]) -> None:
    print(json.dumps(trace, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="HydroGuard demo CLI")
    parser.add_argument("--text", type=str, default=None, help="User text input")
    parser.add_argument("--image", type=str, default=None, help="Path to a plant image")
    parser.add_argument("--sensors", type=str, default=None, help="Path to a JSON file of sensor data")
    parser.add_argument("--interactive", action="store_true", help="Run an interactive demo loop")
    args = parser.parse_args()

    if args.interactive:
        print("HydroGuard interactive demo. Type 'quit' to exit.")
        while True:
            user_text = input("\nYou: ").strip()
            if user_text.lower() in {"quit", "exit"}:
                break
            trace = process_request(text=user_text)
            _print_trace(trace)
        return

    sensor_data = None
    if args.sensors:
        with open(args.sensors, "r", encoding="utf-8") as f:
            sensor_data = json.load(f)

    trace = process_request(text=args.text, image_path=args.image, sensor_data=sensor_data)
    _print_trace(trace)


if __name__ == "__main__":
    main()
