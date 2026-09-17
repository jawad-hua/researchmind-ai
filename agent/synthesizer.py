"""
Synthesizer — the core report-writing step.

Takes evidence bundles from every sub-question and produces a single,
well-structured markdown report with inline citations, then appends
a deduplicated source list.

prepare_synthesis() builds the prompt and does all the citation-ID
bookkeeping once; both the non-streaming path (build_report) and the
streaming path (synthesize_stream, used by the backend's SSE endpoint)
call it, so there is exactly one place that can get citation numbering
wrong instead of two copies drifting apart.
"""

import re
from collections.abc import Iterator

from utils.llm_client import chat, chat_stream

SYNTH_SYSTEM_PROMPT = """You are a senior research analyst writing a report.

Rules:
- Write in clear, structured markdown: an intro, thematic sections with
  headers (##), and a conclusion.
- Every factual claim MUST cite its source inline using ONLY standard
  ASCII square brackets, exactly like [S1], [S2] — never full-width or
  any other bracket style, and never a made-up ID.
- Use the EXACT source ID shown immediately before the evidence snippet
  you are drawing from (e.g. a line starting "[S3] ..."). Copy that ID
  precisely — do not renumber, guess, or reuse an ID for a different
  source's content. If you are not certain which ID a fact came from,
  do not cite one rather than cite the wrong one.
- Do not invent facts that aren't in the evidence. If evidence is thin
  on a point, say so briefly rather than fabricating.
- Target length: what the user asked for (e.g. "5-page report" = ~1500-2000 words).
  If no length is specified, aim for a solid 600-900 word report.
- Do not include a "Sources" section yourself — that is appended separately.
"""

SYNTH_TEMPERATURE = 0.3
SYNTH_MAX_TOKENS = 4096


def format_source_index(sources: list[dict]) -> str:
    """Shared helper: the same 'Sn = title' index format used both when
    prompting the synthesizer and when prompting the fact-checker, so
    the fact-checker can actually verify citation accuracy against the
    same reference the synthesizer was given."""
    return "\n".join(f"{s['id']} = {s['title']}" for s in sources)


def normalize_citation_brackets(text: str) -> str:
    """Defensive normalization: models occasionally emit full-width or
    other bracket variants around citation IDs instead of the ASCII
    [S1] style asked for in the prompt. Normalize them so downstream
    citation detection (append_sources_section) works regardless."""
    return re.sub(r"[\u3010\u2018\u2039]\s*(S\d+)\s*[\u3011\u2019\u203a]", r"[\1]", text)


def prepare_synthesis(topic: str, evidence_bundles: list[dict]) -> dict:
    """
    Build the synthesis prompt and do all citation-ID bookkeeping.

    Returns:
        {
            "prompt": str,
            "system": str,
            "sources": list[dict],       # deduplicated, globally renumbered
            "evidence_blob_for_factcheck": str,
        }
    """
    # Merge evidence text from all sub-questions, with globally unique IDs.
    # Dedup key: URL for web results (same URL = same page). Uploaded
    # documents have no URL (it's always ""), so if we deduped on URL
    # alone every uploaded document would collide into a single source —
    # the first one seen would silently swallow every other document.
    # Fall back to the title (which contains the filename) for those.
    all_sources = []
    combined_evidence = []
    seen_keys = {}

    for bundle in evidence_bundles:
        section_lines = [f"### Sub-question: {bundle['subquestion']}"]
        for source in bundle["sources"]:
            dedup_key = source["url"] or source["title"]
            if dedup_key in seen_keys:
                global_id = seen_keys[dedup_key]
            else:
                global_id = f"S{len(all_sources) + 1}"
                seen_keys[dedup_key] = global_id
                all_sources.append({
                    "id": global_id,
                    "title": source["title"],
                    "url": source["url"],
                })
        # Re-tag evidence text with global IDs for this bundle.
        #
        # IMPORTANT: this must be a single-pass substitution, not
        # sequential .replace() calls. Sequential replacement can
        # cascade-collide — e.g. replacing local [S1] with global [S2]
        # can accidentally get re-matched and mangled by a later step
        # that replaces local [S2] with global [S3], silently merging
        # two different sources under the same citation ID. Building
        # the full local->global map first and substituting in one
        # regex pass avoids that entirely.
        local_to_global = {
            local_source["id"]: seen_keys[local_source["url"] or local_source["title"]]
            for local_source in bundle["sources"]
        }
        evidence_text = re.sub(
            r"\[(S\d+)\]",
            lambda m: f"[{local_to_global.get(m.group(1), m.group(1))}]",
            bundle["evidence_text"],
        )
        section_lines.append(evidence_text)
        combined_evidence.append("\n".join(section_lines))

    evidence_blob = "\n\n---\n\n".join(combined_evidence)

    # A compact index up front gives the model a single place to check
    # "what does Sn actually refer to" instead of having to track IDs
    # purely from scattered mentions inside a long evidence blob — this
    # measurably reduces (though can't fully eliminate) citation
    # mix-ups when many sources are in play.
    source_index = format_source_index(all_sources)

    prompt = f"""Research topic / user request: {topic}

Source index (the ONLY valid citation IDs — double-check against this
list before citing; do not use an ID that isn't here, and do not
attach an ID to content it doesn't actually describe):
{source_index}

Evidence gathered from web research and uploaded documents (cite these
source IDs inline):

{evidence_blob}

Write the full report now."""

    return {
        "prompt": prompt,
        "system": SYNTH_SYSTEM_PROMPT,
        "sources": all_sources,
        "evidence_blob_for_factcheck": f"Source index:\n{source_index}\n\n{evidence_blob}",
    }


def build_report(topic: str, evidence_bundles: list[dict]) -> dict:
    """
    Generate the final report in one shot (non-streaming).

    Returns:
        {
            "report_markdown": str,
            "sources": list[dict],
            "evidence_blob": str,  # pass to fact_check_report
        }
    """
    prep = prepare_synthesis(topic, evidence_bundles)

    report_md = chat(
        prompt=prep["prompt"],
        system=prep["system"],
        temperature=SYNTH_TEMPERATURE,
        max_tokens=SYNTH_MAX_TOKENS,
    )
    report_md = normalize_citation_brackets(report_md)

    return {
        "report_markdown": report_md,
        "sources": prep["sources"],
        "evidence_blob": prep["evidence_blob_for_factcheck"],
    }


def synthesize_stream(prompt: str, system: str) -> Iterator[str]:
    """Thin wrapper so callers (the backend's SSE endpoint) don't need
    to know the model's temperature/token-limit settings — those stay
    defined once, here."""
    yield from chat_stream(
        prompt=prompt,
        system=system,
        temperature=SYNTH_TEMPERATURE,
        max_tokens=SYNTH_MAX_TOKENS,
    )


def append_sources_section(report_markdown: str, sources: list[dict]) -> str:
    """
    Append a formatted Sources section, listing only the sources the
    report actually cites.

    Search results are noisy: a query can pull back pages that match a
    keyword but have nothing to do with the topic, and the LLM correctly
    ignores those when writing. Listing every retrieved source anyway
    would pad the bibliography with entries no sentence in the report
    relies on, so the list is filtered down to the [Sn] markers that
    appear in the body.
    """
    if not sources:
        return report_markdown

    cited = [s for s in sources if f"[{s['id']}]" in report_markdown]
    if not cited:
        # Nothing matched (unusual — e.g. the model dropped the markers).
        # Fall back to listing everything rather than showing no sources.
        cited = sources

    lines = ["\n\n## Sources\n"]
    for s in cited:
        if s["url"]:
            lines.append(f"- [{s['id']}] [{s['title']}]({s['url']})")
        else:
            # Uploaded documents have no URL — show the title plainly,
            # not as a dead markdown link.
            lines.append(f"- [{s['id']}] {s['title']}")

    return report_markdown + "\n".join(lines)
