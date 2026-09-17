import io

from agent.document_loader import chunk_text, extract_text_from_pdf


def test_extract_text_from_pdf_returns_readable_text(sample_pdf_bytes):
    text = extract_text_from_pdf(io.BytesIO(sample_pdf_bytes))
    assert "generative AI" in text
    assert "retrieval augmented generation" in text


def test_chunk_text_respects_overlap_and_size():
    text = "a" * 250
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    # consecutive chunks should share the overlap region
    assert chunks[0][-20:] == chunks[1][:20]


def test_chunk_text_empty_input_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_short_input_returns_single_chunk():
    chunks = chunk_text("short text", chunk_size=1000, overlap=150)
    assert chunks == ["short text"]
