import pytest
from fastapi.testclient import TestClient

import backend.main as backend_main


@pytest.fixture
def client(patch_vector_store_default_embedding):
    return TestClient(backend_main.app)


def test_health_reports_key_configuration(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "groq_key_configured" in body
    assert "tavily_key_configured" in body


def test_create_session_returns_unique_ids(client):
    r1 = client.post("/sessions")
    r2 = client.post("/sessions")
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["session_id"] != r2.json()["session_id"]


def test_unknown_session_returns_404(client):
    r = client.get("/sessions/does-not-exist/documents")
    assert r.status_code == 404


def test_upload_document_indexes_and_lists_it(client, sample_pdf_bytes):
    session_id = client.post("/sessions").json()["session_id"]

    r = client.post(
        f"/sessions/{session_id}/documents",
        files={"files": ("sample.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200
    indexed = r.json()["indexed"]
    assert len(indexed) == 1
    assert indexed[0]["name"] == "sample.pdf"
    assert "source_key" in indexed[0]

    r2 = client.get(f"/sessions/{session_id}/documents")
    assert r2.json()["indexed"] == indexed


def test_upload_rejects_non_pdf(client):
    session_id = client.post("/sessions").json()["session_id"]
    r = client.post(
        f"/sessions/{session_id}/documents",
        files={"files": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


def test_delete_document_removes_it(client, sample_pdf_bytes):
    session_id = client.post("/sessions").json()["session_id"]
    upload = client.post(
        f"/sessions/{session_id}/documents",
        files={"files": ("sample.pdf", sample_pdf_bytes, "application/pdf")},
    ).json()
    source_key = upload["indexed"][0]["source_key"]

    r = client.delete(f"/sessions/{session_id}/documents/{source_key}")
    assert r.status_code == 200

    r2 = client.get(f"/sessions/{session_id}/documents")
    assert r2.json()["indexed"] == []


def test_delete_unknown_document_404s(client):
    session_id = client.post("/sessions").json()["session_id"]
    r = client.delete(f"/sessions/{session_id}/documents/nonexistent-key")
    assert r.status_code == 404


def test_research_end_to_end_with_documents_and_web(client, sample_pdf_bytes, mock_llm, mock_web_search):
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/documents",
        files={"files": ("sample.pdf", sample_pdf_bytes, "application/pdf")},
    )

    r = client.post(
        f"/sessions/{session_id}/research",
        json={"topic": "test topic", "results_per_subquestion": 3, "run_fact_check": True},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source_count"] > 0
    assert "Fact-Check Notes" in data["report_markdown"]
    assert len(data["subquestions"]) > 0


def test_research_without_fact_check(client, mock_llm, mock_web_search):
    session_id = client.post("/sessions").json()["session_id"]
    r = client.post(
        f"/sessions/{session_id}/research",
        json={"topic": "test", "results_per_subquestion": 3, "run_fact_check": False},
    )
    assert r.status_code == 200
    assert "Fact-Check Notes" not in r.json()["report_markdown"]


def test_research_with_no_evidence_returns_502(client, monkeypatch, mock_llm):
    import agent.search as search_module
    import backend.main as backend_main

    def empty_search(q, max_results=5):
        return [], None

    monkeypatch.setattr(search_module, "search_web", empty_search)
    monkeypatch.setattr(backend_main, "search_web", empty_search)

    session_id = client.post("/sessions").json()["session_id"]
    r = client.post(
        f"/sessions/{session_id}/research",
        json={"topic": "test", "results_per_subquestion": 3, "run_fact_check": False},
    )
    assert r.status_code == 502


def test_research_surfaces_llm_error_with_detail(client, monkeypatch, mock_web_search):
    import agent.planner as planner_module

    def broken_chat(**kwargs):
        raise RuntimeError("simulated LLM outage")

    monkeypatch.setattr(planner_module, "chat", broken_chat)

    session_id = client.post("/sessions").json()["session_id"]
    r = client.post(
        f"/sessions/{session_id}/research",
        json={"topic": "test", "results_per_subquestion": 3, "run_fact_check": False},
    )
    assert r.status_code == 502
    assert "simulated LLM outage" in r.json()["detail"]


def _parse_sse(raw_text: str) -> list[tuple[str, object]]:
    """Parse a raw SSE response body into a list of (event, data) pairs."""
    import json as _json
    events = []
    for block in raw_text.strip().split("\n\n"):
        if not block.strip():
            continue
        event_line, data_line = block.split("\n", 1)
        event = event_line.removeprefix("event: ")
        data = _json.loads(data_line.removeprefix("data: "))
        events.append((event, data))
    return events


def test_research_stream_emits_status_token_and_done_events(
    client, mock_llm, mock_llm_stream, mock_web_search
):
    session_id = client.post("/sessions").json()["session_id"]
    r = client.post(
        f"/sessions/{session_id}/research/stream",
        json={"topic": "test topic", "results_per_subquestion": 3, "run_fact_check": True},
    )
    assert r.status_code == 200

    events = _parse_sse(r.text)
    event_types = [e for e, _ in events]

    assert "status" in event_types
    assert "token" in event_types
    assert event_types[-1] == "done"

    # The concatenated token deltas should reconstruct the streamed report
    tokens = [data for event, data in events if event == "token"]
    assert "".join(tokens) == "Report body citing [S1]."

    done_data = events[-1][1]
    assert "Fact-Check Notes" in done_data["report_markdown"]
    assert done_data["source_count"] > 0


def test_research_stream_emits_error_event_on_no_evidence(client, mock_llm, monkeypatch):
    import agent.search as search_module
    import backend.main as backend_main

    monkeypatch.setattr(search_module, "search_web", lambda q, max_results=5: ([], None))
    monkeypatch.setattr(backend_main, "search_web", lambda q, max_results=5: ([], None))

    session_id = client.post("/sessions").json()["session_id"]
    r = client.post(
        f"/sessions/{session_id}/research/stream",
        json={"topic": "test", "results_per_subquestion": 3, "run_fact_check": False},
    )
    assert r.status_code == 200  # the HTTP request itself succeeds; the error is an SSE event
    events = _parse_sse(r.text)
    assert events[-1][0] == "error"
