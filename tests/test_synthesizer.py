from agent.extractor import extract_evidence
from agent.synthesizer import append_sources_section, build_report


def test_multiple_uploaded_documents_stay_distinct(mock_llm):
    """
    Regression test: uploaded documents have no URL, so an earlier
    version of the dedup logic (keying on URL alone) collapsed every
    uploaded document into a single source, silently discarding all
    but the first.
    """
    bundle = extract_evidence("q", [
        {"title": "Uploaded document: a.pdf", "url": "", "content": "A"},
        {"title": "Uploaded document: b.pdf", "url": "", "content": "B"},
    ])
    result = build_report("topic", [bundle])
    titles = {s["title"] for s in result["sources"]}
    assert titles == {"Uploaded document: a.pdf", "Uploaded document: b.pdf"}


def test_no_citation_id_collision_across_bundles(monkeypatch):
    """
    Regression test: retagging local per-bundle IDs to global IDs used
    to do sequential string .replace() calls, which could cascade —
    replacing local [S1] with global [S2] and then replacing local [S2]
    with global [S3] would also corrupt the *already-replaced* [S2],
    merging two unrelated sources under the same citation ID.
    """
    import agent.synthesizer as synth_module
    monkeypatch.setattr(synth_module, "chat", lambda **kw: "placeholder")

    bundle1 = extract_evidence("q1", [
        {"title": "Doc One", "url": "", "content": "x"},
    ])
    bundle2 = extract_evidence("q2", [
        {"title": "Web Article", "url": "https://example.com/x", "content": "y"},
        {"title": "Doc Two", "url": "", "content": "z"},
    ])

    result = build_report("topic", [bundle1, bundle2])
    blob = result["evidence_blob"]

    # Each source's tag must appear exactly once, paired with its own title.
    for s in result["sources"]:
        assert blob.count(f"[{s['id']}] {s['title']}") == 1


def test_source_index_included_in_prompt(monkeypatch):
    """The synthesizer prompt should give the model an explicit
    id->title index to check citations against."""
    import agent.synthesizer as synth_module
    captured = {}

    def fake_chat(prompt, system, temperature, max_tokens):
        captured["prompt"] = prompt
        return "placeholder"

    monkeypatch.setattr(synth_module, "chat", fake_chat)

    bundle = extract_evidence("q", [{"title": "Some Source", "url": "https://example.com/s", "content": "x"}])
    build_report("topic", [bundle])

    assert "Source index" in captured["prompt"]
    assert "Some Source" in captured["prompt"]


def test_append_sources_filters_uncited_sources():
    sources = [
        {"id": "S1", "title": "Cited Source", "url": "https://example.com/a"},
        {"id": "S2", "title": "Uncited Junk", "url": "https://example.com/b"},
    ]
    report = "Body text citing only [S1]."
    final = append_sources_section(report, sources)
    assert "Cited Source" in final
    assert "Uncited Junk" not in final


def test_append_sources_falls_back_to_all_when_none_match():
    """If the model drops citation markers entirely, show every
    source rather than an empty bibliography."""
    sources = [{"id": "S1", "title": "Some Source", "url": "https://example.com/a"}]
    final = append_sources_section("No citation markers here.", sources)
    assert "Some Source" in final


def test_fullwidth_brackets_normalized_to_ascii(monkeypatch):
    """Models occasionally emit \u3010S1\u3011 instead of the requested [S1]; the
    synthesizer should normalize this so citation filtering still works."""
    import agent.synthesizer as synth_module
    monkeypatch.setattr(
        synth_module, "chat",
        lambda **kw: "Report citing \u3010S1\u3011 only."
    )

    bundle = extract_evidence("q", [
        {"title": "Good Source", "url": "https://example.com/good", "content": "x"},
    ])
    result = build_report("topic", [bundle])
    assert "[S1]" in result["report_markdown"]

    final = append_sources_section(result["report_markdown"], result["sources"])
    assert "Good Source" in final
