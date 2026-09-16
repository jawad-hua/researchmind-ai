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
- If the topic is vague, unclear, or garbled, use your best judgement to
  infer what the user most likely means before decomposing it — don't
  take a confusing phrase over-literally and wander into an unrelated
  subject.
"""

PLANNER_WITH_DOCS_SUFFIX = """

The user has also uploaded these documents, which will be searched
alongside the web: {doc_names}.
If the topic is ambiguous, or plausibly refers to the content of these
documents (e.g. asking to summarize, explain, or expand on "the
document" / "the file" / "the second one"), prioritize sub-questions
that would surface the actual content of these documents over generic
web-only interpretations.
"""


def plan_subquestions(topic: str, uploaded_doc_names: list[str] | None = None) -> list[str]:
    """
    Return a list of 3-4 sub-questions for the given research topic.
    Falls back to the raw topic as a single question if parsing fails.

    uploaded_doc_names: filenames of any documents indexed for this
    session, so the planner can ground an ambiguous query in what the
    user actually uploaded instead of interpreting it purely literally.
    """
    system_prompt = PLANNER_SYSTEM_PROMPT
    if uploaded_doc_names:
        system_prompt += PLANNER_WITH_DOCS_SUFFIX.format(
            doc_names=", ".join(uploaded_doc_names)
        )

    raw = chat(
        prompt=f"Topic: {topic}",
        system=system_prompt,
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
