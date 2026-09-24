"""
agents/knowledge_agent.py
----------------------------
Answers general hydroponics questions ("what does high EC mean?"). This is
the "conversational" agent -- it never proposes actuator actions; the
controller agent is the only one that does that.
"""

from __future__ import annotations

from typing import Any, Dict

from app.llm.client import answer_knowledge_question
from app.logger import log_event


def run_knowledge_agent(question: str, context: str = "") -> Dict[str, Any]:
    answer = answer_knowledge_question(question, context)
    result = {"question": question, "answer": answer}
    log_event(component="KNOWLEDGE_AGENT", event="answer_question", result="OK", details=result)
    return result
