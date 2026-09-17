from agent.extractor import collect_all_evidence, extract_evidence


def test_extract_evidence_assigns_local_ids_and_sources():
    results = [
        {"title": "Article A", "url": "https://example.com/a", "content": "Some content here."},
        {"title": "Article B", "url": "https://example.com/b", "content": "More content."},
    ]
    bundle = extract_evidence("What is X?", results)

    assert bundle["subquestion"] == "What is X?"
    assert [s["id"] for s in bundle["sources"]] == ["S1", "S2"]
    assert "[S1] Article A" in bundle["evidence_text"]
    assert "[S2] Article B" in bundle["evidence_text"]


def test_extract_evidence_handles_no_results():
    bundle = extract_evidence("What is X?", [])
    assert bundle["sources"] == []
    assert "No results found" in bundle["evidence_text"]


def test_collect_all_evidence_carries_search_errors():
    def failing_search(q):
        return [], "simulated network error"

    bundles = collect_all_evidence(["q1", "q2"], search_fn=failing_search)
    assert len(bundles) == 2
    assert all(b["error"] == "simulated network error" for b in bundles)
    assert all(b["sources"] == [] for b in bundles)


def test_collect_all_evidence_no_error_on_success():
    def working_search(q):
        return [{"title": "T", "url": "https://example.com", "content": "c"}], None

    bundles = collect_all_evidence(["q1"], search_fn=working_search)
    assert bundles[0]["error"] is None
    assert len(bundles[0]["sources"]) == 1
