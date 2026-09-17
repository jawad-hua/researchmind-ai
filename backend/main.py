"""
ResearchMind AI — FastAPI backend.

Wraps the existing agent pipeline (planner, search, extractor,
synthesizer, fact-checker, vector store, document loader) as HTTP
endpoints, so the Streamlit app (or any other client) talks to a
proper API instead of importing agent modules directly.

Session model: a FastAPI process stays alive across requests (unlike
a Streamlit script, which reruns top-to-bottom on every interaction),
so per-session state — the vector store and which documents are
indexed — lives in a plain in-memory dict keyed by session_id. This
is intentionally simple for Phase 3; swap SESSIONS for Redis or a
database if this ever needs to survive a server restart or run behind
multiple backend replicas.
"""

import os
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.planner import plan_subquestions
from agent.search import search_web
from agent.extractor import collect_all_evidence
from agent.synthesizer import build_report, append_sources_section
from agent.fact_checker import fact_check_report
from agent.document_loader import extract_text_from_pdf, chunk_text
from agent.vector_store import DocumentVectorStore

app = FastAPI(title="ResearchMind AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to the frontend's real origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> {"vector_store": DocumentVectorStore, "indexed_files": {key: name}}
SESSIONS: dict[str, dict] = {}


def _get_session(session_id: str) -> dict:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Unknown session_id. Create one via POST /sessions first.")
    return SESSIONS[session_id]


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    session_id: str


class ResearchRequest(BaseModel):
    topic: str
    results_per_subquestion: int = 5
    run_fact_check: bool = True


class ResearchResponse(BaseModel):
    report_markdown: str
    subquestions: list[str]
    source_count: int


class DocumentEntry(BaseModel):
    source_key: str
    name: str


class DocumentsResponse(BaseModel):
    indexed: list[DocumentEntry]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "groq_key_configured": bool(os.getenv("GROQ_API_KEY")),
        "tavily_key_configured": bool(os.getenv("TAVILY_API_KEY")),
    }


@app.post("/sessions", response_model=SessionResponse)
def create_session():
    """Start a new research session. Call this once per user/browser tab."""
    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = {
        "vector_store": DocumentVectorStore(collection_name=f"session_{session_id}"),
        "indexed_files": {},  # source_key -> display name
    }
    return SessionResponse(session_id=session_id)


@app.post("/sessions/{session_id}/documents", response_model=DocumentsResponse)
def upload_documents(session_id: str, files: list[UploadFile] = File(...)):
    """Upload one or more PDFs to be researched alongside the web for this session."""
    session = _get_session(session_id)
    vector_store: DocumentVectorStore = session["vector_store"]

    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Only PDF files are supported: {f.filename}")

        try:
            text = extract_text_from_pdf(f.file)
            chunks = chunk_text(text)
            source_key = f"{f.filename}::{uuid.uuid4().hex[:8]}"
            vector_store.add_document(f.filename, chunks, source_key=source_key)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to index {f.filename}: {e}")

        session["indexed_files"][source_key] = f.filename

    return DocumentsResponse(indexed=[
        DocumentEntry(source_key=k, name=v) for k, v in session["indexed_files"].items()
    ])


@app.get("/sessions/{session_id}/documents", response_model=DocumentsResponse)
def list_documents(session_id: str):
    session = _get_session(session_id)
    return DocumentsResponse(indexed=[
        DocumentEntry(source_key=k, name=v) for k, v in session["indexed_files"].items()
    ])


@app.delete("/sessions/{session_id}/documents/{source_key}")
def remove_document(session_id: str, source_key: str):
    session = _get_session(session_id)
    if source_key not in session["indexed_files"]:
        raise HTTPException(status_code=404, detail="No such document in this session.")
    session["vector_store"].remove_document(source_key)
    del session["indexed_files"][source_key]
    return {"removed": source_key}


@app.post("/sessions/{session_id}/research", response_model=ResearchResponse)
def research(session_id: str, req: ResearchRequest):
    """Run the full pipeline: plan -> search (web + documents) -> synthesize -> fact-check."""
    session = _get_session(session_id)
    vector_store: DocumentVectorStore = session["vector_store"]

    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="Server is missing GROQ_API_KEY.")

    doc_names = list(session["indexed_files"].values()) or None

    try:
        subquestions = plan_subquestions(req.topic, uploaded_doc_names=doc_names)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planning step failed (LLM call): {e}")

    def combined_search(q: str):
        web_results, error = search_web(q, max_results=req.results_per_subquestion)
        doc_results = vector_store.query(q, top_k=3) if vector_store.has_documents() else []
        return doc_results + web_results, error

    evidence_bundles = collect_all_evidence(subquestions, search_fn=combined_search)
    total_sources = sum(len(b["sources"]) for b in evidence_bundles)

    if total_sources == 0:
        errors = [b["error"] for b in evidence_bundles if b.get("error")]
        detail = "No evidence found — no web results and no uploaded documents matched."
        if errors:
            detail += f" Error: {errors[0]}"
        raise HTTPException(status_code=502, detail=detail)

    try:
        result = build_report(req.topic, evidence_bundles)
        report_md = result["report_markdown"]
        sources = result["sources"]

        if req.run_fact_check:
            fact_check_notes = fact_check_report(report_md, result["evidence_blob"])
            report_md = report_md + f"\n\n{fact_check_notes}"
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Report generation failed (LLM call): {e}")

    final_report = append_sources_section(report_md, sources)

    # Count what the report actually cites, not what retrieval returned —
    # append_sources_section drops uncited results, so the raw retrieval
    # count would overstate what the user sees.
    cited_count = sum(1 for s in sources if f"[{s['id']}]" in final_report)

    return ResearchResponse(
        report_markdown=final_report,
        subquestions=subquestions,
        source_count=cited_count,
    )
