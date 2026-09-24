"""
preprocessing/drosophila_preprocessor.py
-----------------------------------------
An ENGINEERING-INSPIRED abstraction, loosely inspired by ideas from insect
(Drosophila) sensory processing. This is NOT a simulation of real neural
circuitry -- it is a small, explainable set of signal-processing steps that
happen to share names with biological concepts because they were the
original inspiration for the design.

The five "inspired" ideas and how they map to plain Python:

1. Sparse processing:
   Only produce output when a signal is meaningfully outside its normal
   band -- like sparse neural firing, most "channels" stay quiet most of
   the time.
   -> Implemented as: only include a field in `changed_fields` if it
      crossed a threshold.

2. Parallel processing:
   Every sensor channel (pH, EC, temperature, ...) is evaluated
   independently and simultaneously, not as one big combined formula.
   -> Implemented as: a dict comprehension processing each sensor with its
      own independent rule.

3. Inhibitory / filtering behaviour:
   Small, expected fluctuations are suppressed (filtered out) so they
   don't trigger a "state change" -- like lateral inhibition sharpening a
   signal by damping noise.
   -> Implemented as: a `noise_margin` dead-zone around the previous value.

4. Adaptive response to change:
   The system reacts more strongly to a RAPID change than to a slow drift
   at the same absolute level.
   -> Implemented as: `delta` comparison against the previous reading.

5. Temporal change detection:
   Comparing "now" to "a moment ago" to detect a *change*, not just an
   absolute value.
   -> Implemented as: the `previous` snapshot stored between calls.

Input:  raw sensor dict (e.g. {"temperature": 31.2, "ph": 6.9, ...})
Output: compact categorical state, e.g.
    {
      "temperature_state": "HIGH",
      "ph_state": "NORMAL",
      "ec_state": "HIGH",
      "water_level_state": "LOW",
      "overall_state": "STRESS",
      "changed_fields": ["temperature", "water_level"]
    }

This compact state -- not the raw numbers -- is what gets handed to the
controller agent, which is the "long-context handling" strategy described
in the README/learning guide: send a small, meaningful summary instead of
a firehose of raw numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

# Example operational thresholds. THESE ARE CONFIGURABLE EXAMPLES, not
# universal truths for every crop/hydroponic system -- see README
# "limitations" for why they must be tuned per deployment.
THRESHOLDS = {
    "ph": {"low": 5.5, "high": 6.5},
    "ec": {"low": 1.2, "high": 2.2},
    "temperature": {"low": 18.0, "high": 28.0},
    "humidity": {"low": 40.0, "high": 80.0},
    "water_level": {"low": 30.0, "high": 100.0},
    "light_intensity": {"low": 150.0, "high": 800.0},
}

# "Inhibitory" dead-zone: a change smaller than this (in absolute units) is
# treated as noise and does not count as a meaningful temporal change.
NOISE_MARGIN = {
    "ph": 0.1,
    "ec": 0.1,
    "temperature": 0.5,
    "humidity": 2.0,
    "water_level": 2.0,
    "light_intensity": 20.0,
}


def _classify(value: Optional[float], key: str) -> str:
    """Sparse + parallel step: classify one channel independently."""
    if value is None:
        return "UNKNOWN"
    bounds = THRESHOLDS.get(key)
    if not bounds:
        return "UNKNOWN"
    if value < bounds["low"]:
        return "LOW"
    if value > bounds["high"]:
        return "HIGH"
    return "NORMAL"


@dataclass
class DrosophilaPreprocessor:
    """
    Stateful preprocessor: keeps the previous reading so it can detect
    temporal change (idea #4 and #5 above). Create one instance and reuse
    it across calls (e.g. one per running system).
    """

    previous: Optional[Dict[str, float]] = None

    def process(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        changed_fields = []
        states: Dict[str, str] = {}

        for key in THRESHOLDS:
            value = raw.get(key)
            state = _classify(value, key)
            states[f"{key}_state"] = state

            if value is not None and self.previous is not None:
                prev_value = self.previous.get(key)
                if prev_value is not None:
                    delta = abs(value - prev_value)
                    if delta > NOISE_MARGIN.get(key, 0):
                        changed_fields.append(key)

        # Overall state: sparse "any abnormal channel" -> STRESS, else NORMAL.
        abnormal = any(v in ("LOW", "HIGH") for v in states.values())
        overall_state = "STRESS" if abnormal else "NORMAL"

        result = {**states, "overall_state": overall_state, "changed_fields": changed_fields}

        # Update stored "previous" snapshot for the next temporal comparison.
        self.previous = {k: raw.get(k) for k in THRESHOLDS if raw.get(k) is not None}

        return result
