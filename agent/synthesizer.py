"""
Synthesizer — the core report-writing step.

Takes evidence bundles from every sub-question and produces a single,
well-structured markdown report with inline citations, then appends
a deduplicated source list.
"""

from utils.llm_client import chat

SYNTH_SYSTEM_PROMPT = """You are a senior research analyst writing a report.

Rules:
- Write in clear, structured markdown: an intro, thematic sections with
  headers (##), and a conclusion.
- Every factual claim MUST cite its source inline like [S1], [S2] etc.,
  using the source IDs given in the evidence.
- Do not invent facts that aren't in the evidence. If evidence is thin
  on a point, say so briefly rather than fabricating.
- Target length: what the user asked for (e.g. "5-page report" = ~1500-2000 words).
  If no length is specified, aim for a solid 600-900 word report.
- Do not include a "Sources" section yourself — that is appended separately.
"""


def build_report(topic: str, evidence_bundles: list[dict]) -> dict:
    """
    Generate the final report.

    Returns:
        {
            "report_markdown": str,
            "sources": list[dict]  # deduplicated, renumbered globally
        }
    """
    # Merge evidence text from all sub-questions, with globally unique IDs
    all_sources = []
    combined_evidence = []
    seen_urls = {}

    for bundle in evidence_bundles:
        section_lines = [f"### Sub-question: {bundle['subquestion']}"]
        for source in bundle["sources"]:
            if source["url"] in seen_urls:
                global_id = seen_urls[source["url"]]
            else:
                global_id = f"S{len(all_sources) + 1}"
                seen_urls[source["url"]] = global_id
                all_sources.append({
                    "id": global_id,
                    "title": source["title"],
                    "url": source["url"],
                })
        # Re-tag evidence text with global IDs for this bundle
        evidence_text = bundle["evidence_text"]
        for local_source in bundle["sources"]:
            global_id = seen_urls[local_source["url"]]
            evidence_text = evidence_text.replace(
                f"[{local_source['id']}]", f"[{global_id}]"
            )
        section_lines.append(evidence_text)
        combined_evidence.append("\n".join(section_lines))

    evidence_blob = "\n\n---\n\n".join(combined_evidence)

    prompt = f"""Research topic / user request: {topic}

Evidence gathered from web research (cite these source IDs inline):

{evidence_blob}

Write the full report now."""

    report_md = chat(
        prompt=prompt,
        system=SYNTH_SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=4096,
    )

    return {
        "report_markdown": report_md,
        "sources": all_sources,
    }


def append_sources_section(report_markdown: str, sources: list[dict]) -> str:
    """Append a formatted Sources section to the report."""
    if not sources:
        return report_markdown

    lines = ["\n\n## Sources\n"]
    for s in sources:
        lines.append(f"- [{s['id']}] [{s['title']}]({s['url']})")

    return report_markdown + "\n".join(lines)
