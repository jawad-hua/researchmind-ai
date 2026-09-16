"""
Vector Store — wraps a per-session, in-memory Chroma collection for
retrieval-augmented research over uploaded documents.

Ephemeral by design: each Streamlit session gets its own instance, so
one user's uploaded documents never leak into another's, and nothing
is written to disk.
"""

import chromadb


class DocumentVectorStore:
    """Thin wrapper around a single Chroma collection."""

    def __init__(self, collection_name: str = "documents", embedding_function=None):
        """
        collection_name MUST be unique per user session. Chroma's
        EphemeralClient shares its underlying in-memory system across
        instances in the same process (by design, for notebook-style
        reuse) — so if every session used the same collection name,
        one user's uploaded documents would leak into another user's
        queries. Passing a per-session name (e.g. a random session id)
        keeps sessions isolated even though the backend is shared.

        embedding_function is optional and exists mainly for testability
        (inject a fake one to test add/query logic without downloading
        the real embedding model). Leave it unset in production to use
        Chroma's bundled default local embedding model.
        """
        self._client = chromadb.EphemeralClient()
        kwargs = {"name": collection_name}
        if embedding_function is not None:
            kwargs["embedding_function"] = embedding_function
        self._collection = self._client.get_or_create_collection(**kwargs)

    def add_document(self, source_name: str, chunks: list[str], source_key: str | None = None) -> None:
        """
        Embed and store the chunks of one uploaded document.

        source_key is a stable identifier used for later removal (e.g.
        "filename::filesize"). It defaults to source_name if not given,
        but the caller should pass something unique when two uploads
        could share the same display name.
        """
        if not chunks:
            return
        key = source_key or source_name
        ids = [f"{key}-{i}" for i in range(len(chunks))]
        metadatas = [{"source": source_name, "source_key": key} for _ in chunks]
        self._collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    def remove_document(self, source_key: str) -> None:
        """Remove every chunk previously added under this source_key —
        used when the user removes a file from the uploader, so stale
        content doesn't keep influencing retrieval."""
        if self._collection.count() == 0:
            return
        self._collection.delete(where={"source_key": source_key})

    def has_documents(self) -> bool:
        return self._collection.count() > 0

    def query(self, query_text: str, top_k: int = 3) -> list[dict]:
        """
        Return the top_k most relevant chunks, shaped exactly like
        agent.search.search_web results ({title, url, content}) so they
        can flow through the existing extractor/synthesizer unchanged.
        """
        count = self._collection.count()
        if count == 0:
            return []

        results = self._collection.query(
            query_texts=[query_text],
            n_results=min(top_k, count),
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        out = []
        for doc, meta in zip(docs, metas):
            out.append({
                "title": f"Uploaded document: {meta.get('source', 'unknown')}",
                "url": "",
                "content": doc,
            })
        return out
