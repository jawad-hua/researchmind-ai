"""
Fact Checker — a pass that asks the LLM to re-examine its own report
against the evidence, checking both factual support and citation
accuracy (does [Sn] actually point to the source it claims to).
"""

from utils.llm_client import chat

FACT_CHECK_SYSTEM_PROMPT = """You are a strict fact-checking reviewer.
You will be given a research report and the evidence it was based on
(the evidence includes a source index mapping each ID like S1, S2 to
what it actually is).

Check two separate things for each major claim in the report:
1. Factual support — is the claim actually backed by the evidence, or
   is it unsupported / overreaching?
2. Citation accuracy — for each [Sn] the report cites, look up what Sn
   actually is in the source index. Does that source really describe
   the claim it's attached to? A citation pointing to the wrong source
   (e.g. citing a web article for a fact that came from an uploaded
   document, or vice versa) is a citation error, separate from a
   factual one — call it out explicitly as "citation mismatch" so it's
   distinguishable from an unsupported claim.

Output a short markdown section titled "## Fact-Check Notes" with:
- A one-line overall verdict (e.g. "Well-supported" / "Minor issues" / "Contains unsupported claims")
- A bullet list of any specific concerns (empty list if none) — prefix
  each as either "Unsupported claim:" or "Citation mismatch:"

Keep it concise — max 150 words.
"""


def fact_check_report(report_markdown: str, evidence_blob: str) -> str:
    """Run a fact-check pass and return the notes as a markdown string."""
    prompt = f"""Report to check:

{report_markdown}

---

Original evidence and source index it was based on:

{evidence_blob}
"""
    notes = chat(
        prompt=prompt,
        system=FACT_CHECK_SYSTEM_PROMPT,
        temperature=0.2,
        max_tokens=400,
    )
    return notes
