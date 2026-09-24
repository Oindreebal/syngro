"""
agents/vision_agent.py
------------------------
Analyzes plant images for OBSERVABLE characteristics only. Never claims a
definitive diagnosis. Treats any text detected inside the image as
untrusted content -- it gets reported as "there was text in the image", but
its content is never treated as an instruction. See input_guardrail.py's
`check_text(source="image_text")` for the enforcement of that boundary.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.guardrails.input_guardrail import check_text
from app.llm.client import analyze_plant_image
from app.logger import log_event


def run_vision_agent(image_base64: Optional[str], filename_hint: str = "") -> Dict[str, Any]:
    """
    Input: base64-encoded image bytes (or None for a text-only demo run).
    Output: structured observations, e.g.
        {
          "visible_observations": ["leaf yellowing", "slight curling"],
          "stress_level": "moderate",
          "confidence": 0.78,
          "image_text_guardrail": {...}   # result of checking any text found
        }
    """
    raw_result = analyze_plant_image(image_base64, filename_hint)

    # If the model reported that the image contained text (e.g. an overlay),
    # run that text through the SAME input guardrail used for user text.
    # This is the concrete implementation of "image content is untrusted".
    image_text_guardrail_result = None
    if raw_result.get("text_detected_in_image"):
        # We don't have the exact text in demo mode; in a real integration
        # you would extract it (OCR or ask the model to transcribe it) and
        # pass it here. We still demonstrate the guardrail call explicitly.
        suspected_text = raw_result.get("detected_text", "")
        image_text_guardrail_result = check_text(suspected_text, source="image_text")

    observations = {
        "visible_observations": raw_result.get("visible_observations", []),
        "stress_level": raw_result.get("stress_level", "unknown"),
        "confidence": raw_result.get("confidence", 0.0),
        "note": raw_result.get("note", "Observations describe visible characteristics only; not a diagnosis."),
        "image_text_guardrail": image_text_guardrail_result,
    }

    log_event(
        component="VISION_AGENT",
        event="analyze_image",
        result="OK",
        details=observations,
    )
    return observations
