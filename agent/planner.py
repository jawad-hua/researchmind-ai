"""
Planner — breaks a broad research query into 3-4 focused sub-questions.

This is the "multi-step agent" part of the pipeline: instead of one
generic search, we decompose the topic so each search call returns
sharper, more relevant results.
"""

import re
from utils.llm_client import chat

PLANNER_SYSTEM_PROMPT = """You are a research planning assistant.
Given a topic, break it into 3-4 specific, well-scoped sub-questions
that together would let someone write a comprehensive report on the topic.

Rules:
- Output ONLY a numbered list, one sub-question per line.
- No preamble, no explanation, no markdown headers.
- Each sub-question should be searchable on the web (specific, not vague).
"""


def plan_subquestions(topic: str) -> list[str]:
    """
    Return a list of 3-4 sub-questions for the given research topic.
    Falls back to the raw topic as a single question if parsing fails.
    """
    raw = chat(
        prompt=f"Topic: {topic}",
        system=PLANNER_SYSTEM_PROMPT,
        temperature=0.4,
        max_tokens=300,
    )

    # Parse numbered list like "1. ..." / "1) ..."
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    questions = []
    for line in lines:
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line)
        if cleaned:
            questions.append(cleaned)

    if not questions:
        questions = [topic]

    return questions[:4]
