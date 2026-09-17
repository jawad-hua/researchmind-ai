from agent.vector_store import DocumentVectorStore


def test_empty_store_has_no_documents(vector_store):
    assert not vector_store.has_documents()
    assert vector_store.query("anything") == []


def test_add_and_query_returns_matching_shape(vector_store):
    vector_store.add_document("doc.pdf", ["Vector databases store embeddings."], source_key="doc.pdf::1")
    assert vector_store.has_documents()

    results = vector_store.query("vector databases", top_k=1)
    assert len(results) == 1
    assert results[0]["title"] == "Uploaded document: doc.pdf"
    assert results[0]["url"] == ""
    assert "embeddings" in results[0]["content"]


def test_remove_document_deletes_only_that_source(vector_store):
    vector_store.add_document("a.pdf", ["Content A"], source_key="a.pdf::1")
    vector_store.add_document("b.pdf", ["Content B"], source_key="b.pdf::1")

    vector_store.remove_document("a.pdf::1")

    titles = [r["title"] for r in vector_store.query("content", top_k=5)]
    assert "Uploaded document: a.pdf" not in titles
    assert "Uploaded document: b.pdf" in titles


def test_two_sessions_are_isolated(fake_embedding_function):
    """
    Regression test: Chroma's EphemeralClient shares its underlying
    in-memory system across instances in the same process. Without a
    unique collection_name per session, one session's documents would
    leak into another's.
    """
    store_a = DocumentVectorStore(collection_name="session_a", embedding_function=fake_embedding_function)
    store_b = DocumentVectorStore(collection_name="session_b", embedding_function=fake_embedding_function)

    store_a.add_document("secret.pdf", ["Only session A should see this."], source_key="secret.pdf::1")

    assert store_a.has_documents()
    assert not store_b.has_documents()
    assert store_b.query("anything") == []
