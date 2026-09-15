"""
Fact Checker — optional pass that asks the LLM to re-examine its own
report against the evidence and flag anything unsupported.

Phase 1 keeps this simple: a single self-review pass, not a separate
verification pipeline. Good enough to demonstrate the concept; can be
made more rigorous (e.g. claim-by-claim source matching) in Phase 3.
"""

from utils.llm_client import chat

FACT_CHECK_SYSTEM_PROMPT = """You are a strict fact-checking reviewer.
You will be given a research report and the evidence it was based on.

Check each major claim in the report:
- Is it actually supported by the cited evidence?
- Are there unsupported or overreaching claims?

Output a short markdown section titled "## Fact-Check Notes" with:
- A one-line overall verdict (e.g. "Well-supported" / "Minor issues" / "Contains unsupported claims")
- A bullet list of any specific concerns (empty list if none)

Keep it concise — max 150 words.
"""


def fact_check_report(report_markdown: str, evidence_blob: str) -> str:
    """Run a fact-check pass and return the notes as a markdown string."""
    prompt = f"""Report to check:

{report_markdown}

---

Original evidence it was based on:

{evidence_blob}
"""
    notes = chat(
        prompt=prompt,
        system=FACT_CHECK_SYSTEM_PROMPT,
        temperature=0.2,
        max_tokens=400,
    )
    return notes
