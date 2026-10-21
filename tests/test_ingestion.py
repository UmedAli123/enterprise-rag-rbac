"""Tests for Phase 1: Ingestion and Vector Search."""

from pathlib import Path
from qdrant_client import QdrantClient
from app.config import settings
from app.ingestion import COLLECTION_NAME, VALID_ACCESS_LEVELS, ingest, load_and_chunk_documents


def test_all_10_documents_ingested():
    """Verify that all 10 documents are found and chunked."""
    docs_path = Path(settings.DATA_DIR) / "nexora_docs"
    chunks = load_and_chunk_documents(docs_path)
    
    unique_doc_ids = {c["doc_id"] for c in chunks}
    assert len(unique_doc_ids) == 10, f"Expected 10 unique documents, got {len(unique_doc_ids)}: {unique_doc_ids}"


def test_chunk_payloads_have_valid_access_levels():
    """Verify that every chunk has a valid access_level from the allowed set."""
    docs_path = Path(settings.DATA_DIR) / "nexora_docs"
    chunks = load_and_chunk_documents(docs_path)

    for chunk in chunks:
        assert chunk["access_level"] in VALID_ACCESS_LEVELS, f"Invalid access level: {chunk['access_level']}"
        assert chunk["doc_id"], "Missing doc_id"
        assert chunk["title"], "Missing title"
        assert chunk["section"], "Missing section"
        assert chunk["text"], "Missing text"


def test_ingestion_idempotence():
    """Verify running ingestion twice results in identical chunk count without duplicates."""
    from app import retrieval
    if retrieval._qdrant_client is not None:
        retrieval._qdrant_client.close()
        retrieval._qdrant_client = None

    count_first = ingest(reset=True)
    assert count_first > 0

    count_second = ingest(reset=False)
    assert count_first == count_second, f"Chunk count changed on second ingestion: {count_first} vs {count_second}"
