from app.services.vector_store import VectorStore


def test_cosine_similarity_prefers_identical_vectors() -> None:
    store = VectorStore()

    assert store._cosine([1, 0], [1, 0]) > store._cosine([1, 0], [0, 1])


def test_metadata_filter_requires_exact_match() -> None:
    store = VectorStore()

    assert store._metadata_matches({"department": "legal"}, {"department": "legal"})
    assert not store._metadata_matches({"department": "finance"}, {"department": "legal"})

