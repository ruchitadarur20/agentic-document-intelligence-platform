import uuid

from app.ingestion.chunking import TextChunker


def test_chunker_adds_metadata_and_stable_chunk_ids() -> None:
    document_id = uuid.uuid4()
    chunks = TextChunker().chunk(document_id, "alpha beta " * 400, {"filename": "sample.txt"})

    assert chunks
    assert chunks[0]["chunk_id"] == f"{document_id}:0"
    assert chunks[0]["metadata"]["filename"] == "sample.txt"
    assert chunks[0]["metadata"]["chunk_index"] == 0

