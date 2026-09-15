"""
Extractor — turns raw search results into a compact evidence bundle
the synthesizer can reason over, and keeps a source registry for
citations.
"""


def extract_evidence(subquestion: str, results: list[dict]) -> dict:
    """
    Take search results for one sub-question and package them as
    evidence with numbered source references.

    Returns:
        {
            "subquestion": str,
            "evidence_text": str,   # concatenated snippets, source-tagged
            "sources": list[dict],  # [{id, title, url}]
        }
    """
    sources = []
    evidence_lines = []

    for i, result in enumerate(results, start=1):
        source_id = f"S{i}"
        sources.append({
            "id": source_id,
            "title": result["title"],
            "url": result["url"],
        })
        snippet = result["content"][:800]  # cap to keep prompt size sane
        evidence_lines.append(f"[{source_id}] {result['title']}\n{snippet}")

    return {
        "subquestion": subquestion,
        "evidence_text": "\n\n".join(evidence_lines) if evidence_lines else "No results found.",
        "sources": sources,
    }


def collect_all_evidence(subquestions: list[str], search_fn) -> list[dict]:
    """
    Run search_fn over every sub-question and extract evidence for each.
    search_fn is injected (search_web) so this module stays testable
    without hitting the network. search_fn must return (results, error).
    Any error is attached to the bundle so the UI can surface it.
    """
    bundles = []
    for sq in subquestions:
        results, error = search_fn(sq)
        bundle = extract_evidence(sq, results)
        bundle["error"] = error
        bundles.append(bundle)
    return bundles
