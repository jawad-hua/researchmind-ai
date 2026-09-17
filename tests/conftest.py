"""
Shared fixtures for the ResearchMind AI test suite.

Nothing here touches the network: LLM calls, web search, and the vector
store's embedding model are all faked, so `pytest` runs offline and
fast. This mirrors the manual testing approach used throughout
development — inject fakes at the same seams the production code
already exposes for testability.
"""

import hashlib
import os

os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("TAVILY_API_KEY", "test-key")

import pytest

from agent.vector_store import DocumentVectorStore


class FakeEmbeddingFunction:
    """A deterministic, offline stand-in for Chroma's default embedding
    model (which needs a network download on first use)."""

    def __call__(self, input):
        return [[b / 255.0 for b in hashlib.md5(t.encode()).digest()[:8]] for t in input]

    def embed_query(self, input):
        return self(input)

    def name(self):
        return "fake"

    def is_legacy(self):
        return False

    @staticmethod
    def build_from_config(config):
        return FakeEmbeddingFunction()

    def get_config(self):
        return {}


@pytest.fixture
def fake_embedding_function():
    return FakeEmbeddingFunction()


@pytest.fixture
def vector_store(fake_embedding_function):
    """A fresh, isolated vector store per test."""
    return DocumentVectorStore(
        collection_name=f"test_{id(object())}",
        embedding_function=fake_embedding_function,
    )


@pytest.fixture
def patch_vector_store_default_embedding(monkeypatch, fake_embedding_function):
    """
    Patch DocumentVectorStore so that ANY instance created during a test
    (e.g. ones the backend creates internally in create_session()) uses
    the fake embedding function instead of trying to download the real
    one. Use this for tests that go through backend.main endpoints
    rather than constructing a DocumentVectorStore directly.
    """
    original_init = DocumentVectorStore.__init__

    def patched_init(self, collection_name="documents", embedding_function=None):
        original_init(
            self,
            collection_name=collection_name,
            embedding_function=embedding_function or fake_embedding_function,
        )

    monkeypatch.setattr(DocumentVectorStore, "__init__", patched_init)


@pytest.fixture
def sample_pdf_bytes(tmp_path):
    """A small real PDF (not a mock) to exercise actual text extraction."""
    from utils.pdf_export import markdown_to_pdf

    out_path = tmp_path / "sample.pdf"
    markdown_to_pdf(
        "## Sample Document\n"
        "This is test content about generative AI trends and vector databases.\n\n"
        "## Second Section\n"
        "This section discusses retrieval augmented generation in depth.",
        title="Sample",
        output_path=str(out_path),
    )
    return out_path.read_bytes()


def make_fake_chat(planner_response="1. First sub-question?\n2. Second sub-question?",
                    report_response="Report body citing [S1].",
                    fact_check_response="## Fact-Check Notes\n- Overall Verdict: Well-supported."):
    """Build a fake `chat(prompt, system, temperature, max_tokens)` that
    routes to a canned response based on which system prompt is asking
    (planner vs synthesizer vs fact-checker each have distinguishable
    system prompts)."""

    def fake_chat(prompt, system, temperature, max_tokens):
        lowered = system.lower()
        if "planning" in lowered or "sub-question" in lowered:
            return planner_response
        if "fact-check" in lowered:
            return fact_check_response
        return report_response

    return fake_chat


@pytest.fixture
def mock_llm(monkeypatch):
    """Patch chat() everywhere it's imported (planner, synthesizer,
    fact_checker each did `from utils.llm_client import chat`, so each
    module has its own reference to patch)."""
    import agent.planner as planner_module
    import agent.synthesizer as synth_module
    import agent.fact_checker as fc_module

    fake = make_fake_chat()
    monkeypatch.setattr(planner_module, "chat", fake)
    monkeypatch.setattr(synth_module, "chat", fake)
    monkeypatch.setattr(fc_module, "chat", fake)
    return fake


@pytest.fixture
def mock_llm_stream(monkeypatch):
    """Patch chat_stream() (used by synthesize_stream) to yield a canned
    response in a few chunks instead of hitting Groq's streaming API."""
    import agent.synthesizer as synth_module

    def fake_chat_stream(prompt, system, temperature, max_tokens):
        for piece in ["Report ", "body ", "citing ", "[S1]."]:
            yield piece

    monkeypatch.setattr(synth_module, "chat_stream", fake_chat_stream)
    return fake_chat_stream


@pytest.fixture
def mock_web_search(monkeypatch):
    """
    Patch search_web wherever it's imported, returning one canned
    result and no error.

    Patching `agent.search.search_web` alone is not enough: backend/
    main.py did `from agent.search import search_web`, which binds its
    own name to the original function at import time. Patching the
    source module doesn't touch that already-bound reference, so the
    backend's copy must be patched separately too.
    """
    import agent.search as search_module

    def fake_search_web(query, max_results=5):
        return (
            [{"title": "Mock Web Result", "url": "https://example.com/mock", "content": "Some mock web content."}],
            None,
        )

    monkeypatch.setattr(search_module, "search_web", fake_search_web)

    try:
        import backend.main as backend_main
        monkeypatch.setattr(backend_main, "search_web", fake_search_web)
    except ImportError:
        pass  # backend not installed/available — fine for agent-only tests

    return fake_search_web
