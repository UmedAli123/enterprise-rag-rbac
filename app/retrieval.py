"""Filtered vector search with RBAC metadata pre-filtering."""

from typing import Any, Dict, List
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.ingestion import COLLECTION_NAME

# Singleton instances for reuse
_qdrant_client = None
_embedder = None


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(path=settings.QDRANT_PATH)
    return _qdrant_client


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedder


def search(query: str, allowed_levels: List[str], k: int = settings.TOP_K) -> List[Dict[str, Any]]:
    """Retrieve top-k chunks with RBAC pre-filtering applied inside Qdrant.

    Args:
        query: User search query or question.
        allowed_levels: Required list of permitted access levels (e.g. ['public', 'hr']).
                        Has no default value.
        k: Number of chunks to retrieve (defaults to settings.TOP_K).

    Returns:
        List of chunk payload dictionaries with score.
        If allowed_levels is empty or None, returns an empty list without querying Qdrant.
    """
    if not allowed_levels:
        return []

    # Clean and lowercase allowed levels
    clean_levels = [lvl.strip().lower() for lvl in allowed_levels if lvl and lvl.strip()]
    if not clean_levels:
        return []

    client = get_qdrant_client()
    embedder = get_embedder()

    # Generate normalized query vector
    query_vector = embedder.encode(query, normalize_embeddings=True).tolist()

    # Apply access_level filter INSIDE the vector search (Pre-filtering)
    qdrant_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="access_level",
                match=models.MatchAny(any=clean_levels)
            )
        ]
    )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=k
    ).points

    retrieved_chunks = []
    for hit in results:
        payload = hit.payload.copy()
        payload["score"] = hit.score
        retrieved_chunks.append(payload)

    return retrieved_chunks
