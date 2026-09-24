"""
router.py
---------
Simple, deterministic Python router: "which agent(s) should handle this
input?" No LLM is used for routing -- a plain rule-based function is easier
to explain, test, and reason about, and routing here doesn't need
open-ended judgement.

Rules (multiple can fire for one request):
  - image present               -> "vision"
  - sensor data present         -> "sensor"
  - text looks like a question  -> "knowledge"
  - text looks like an action
    request (mentions an
    actuator + duration, or an
    imperative verb)            -> "controller"

If nothing matches but there is text, it defaults to "knowledge" so the
user always gets a response rather than silence.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

ACTION_VERBS = re.compile(
    r"\b(turn|switch|start|stop|activate|run|dose|refill|open|close)\b", re.IGNORECASE
)
ACTUATOR_NOUNS = re.compile(r"\b(pump|fan|light|nutrient|valve|water)\b", re.IGNORECASE)
QUESTION_MARKERS = re.compile(r"\?|^\s*(what|why|how|when|does|is|are|can)\b", re.IGNORECASE)


def route(
    text: Optional[str] = None,
    image_base64: Optional[str] = None,
    sensor_data: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Return an ordered list of agent names that should process this input."""
    agents: List[str] = []

    if image_base64:
        agents.append("vision")

    if sensor_data:
        agents.append("sensor")

    if text:
        looks_like_action = bool(ACTION_VERBS.search(text) and ACTUATOR_NOUNS.search(text))
        looks_like_question = bool(QUESTION_MARKERS.search(text))

        if looks_like_action:
            agents.append("controller")
        elif looks_like_question or not agents:
            # Default to knowledge agent for general questions, and also as
            # a fallback so a plain text message always gets *some* response.
            agents.append("knowledge")

    return agents or ["knowledge"]
