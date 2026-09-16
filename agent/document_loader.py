"""
Document Loader — extracts text from uploaded PDFs and splits it into
overlapping chunks suitable for embedding into the vector store.
"""

from pypdf import PdfReader


def extract_text_from_pdf(file) -> str:
    """
    Extract all text from a PDF.
    `file` is a file-like object (works directly with Streamlit's
    UploadedFile, or any open binary file handle).
    """
    reader = PdfReader(file)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """
    Fixed-size character chunking with overlap.

    Good enough for Phase 2 — a smarter sentence/paragraph-aware splitter
    (e.g. recursive splitting on headers, then sentences) can replace this
    later without touching the vector store or retrieval pipeline.
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)
    step = max(chunk_size - overlap, 1)

    while start < n:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks
