"""
guardrails/input_guardrail.py
------------------------------
Checkpoint #1: runs BEFORE any input (text, "image text", etc.) reaches an
agent. Its job is to decide ALLOW or BLOCK, and to never be a black box --
every decision includes a reason.

Design principle (see LEARNING_GUIDE.md): deterministic checks are the
final security boundary. An optional LLM classification (client.py's
`classify_text_safety`) can ADD suspicion signal, but a benign LLM verdict
never overrides a deterministic match, and a "suspicious" LLM verdict alone
(without a deterministic match) does not block a message. This makes the
system's behaviour predictable and testable -- important for something
graded partly on demonstrable guardrails.

We deliberately avoid a "block everything that looks risky" keyword filter.
Instead we use:
  1. A pattern list of well-known override / bypass phrasings, matched with
     some tolerance (case-insensitive substring), for HIGH-CONFIDENCE
     prompt-injection language.
  2. A separate, narrower pattern list for destructive/dangerous requests
     (e.g. shell commands, "delete all files").
  3. A short allowlist of legitimate patterns that should never be blocked
     even if they mention "the pump" or "the system" (e.g. "turn the pump
     on for 30 seconds" is a normal, legitimate action request -- it goes
     on to the action guardrail later, it is not itself malicious input).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app.llm.client import classify_text_safety
from app.logger import log_event

# High-confidence prompt-injection / override phrasing.
INJECTION_PATTERNS: List[str] = [
    r"ignore (all |any |previous |prior )*instructions",
    r"disregard (all |any |previous |prior )*instructions",
    r"disable (the )?safety",
    r"bypass (the )?(guardrail|safety|security|filter)",
    r"override (the )?(system|safety|guardrail)",
    r"you are now (in )?(developer|admin|god) mode",
    r"pretend (you have|to have) no (restrictions|rules)",
    r"reveal (your|the) (system prompt|instructions)",
    r"unrestricted access",
    r"act as if you have no limits",
]

# Destructive / dangerous action-style requests -- these should never reach
# an "execute" pathway; they are blocked as input regardless of framing.
DESTRUCTIVE_PATTERNS: List[str] = [
    r"rm\s+-rf",
    r"delete all files",
    r"drop table",
    r"format (the )?disk",
    r"execute_shell_command",
    r"os\.system",
    r"subprocess\.",
    r"shut ?down the (system|server) permanently",
]

_COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
_COMPILED_DESTRUCTIVE = [re.compile(p, re.IGNORECASE) for p in DESTRUCTIVE_PATTERNS]


def _matches_any(patterns: List[re.Pattern], text: str) -> List[str]:
    return [p.pattern for p in patterns if p.search(text)]


def check_text(user_text: str, source: str = "user_text") -> Dict[str, Any]:
    """
    Evaluate one piece of text (a user message, OR text detected inside an
    image -- callers pass source="image_text" for the latter, which is
    treated identically: untrusted content to be checked, never obeyed).

    Returns:
        {"allowed": bool, "reason": str, "matched_patterns": [...], "llm_signal": {...}}
    """
    text = user_text or ""

    injection_matches = _matches_any(_COMPILED_INJECTION, text)
    destructive_matches = _matches_any(_COMPILED_DESTRUCTIVE, text)

    llm_signal = classify_text_safety(text)

    if destructive_matches:
        result = {
            "allowed": False,
            "reason": "destructive_command_pattern_detected",
            "matched_patterns": destructive_matches,
            "llm_signal": llm_signal,
        }
    elif injection_matches:
        result = {
            "allowed": False,
            "reason": "prompt_injection_pattern_detected",
            "matched_patterns": injection_matches,
            "llm_signal": llm_signal,
        }
    else:
        # No deterministic match -> ALLOW, regardless of LLM suspicion alone.
        # (See module docstring: LLM signal never overrides deterministic
        # ALLOW on its own -- it's recorded for visibility/logging only.)
        result = {
            "allowed": True,
            "reason": "no_malicious_pattern_detected",
            "matched_patterns": [],
            "llm_signal": llm_signal,
        }

    log_event(
        component="INPUT_GUARDRAIL",
        event=f"check_text[{source}]",
        result="ALLOWED" if result["allowed"] else "BLOCKED",
        reason=result["reason"],
        details={"source": source, "text_preview": text[:200], "llm_signal": llm_signal},
    )
    return result
