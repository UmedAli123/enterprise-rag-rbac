"""Debug script to query Qdrant without role filtering."""

import argparse
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Add parent directory to path to import settings
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import settings
from app.ingestion import COLLECTION_NAME


def search_debug(query: str, top_k: int = 5):
    """Search Qdrant collection without filters and print top chunks."""
    client = QdrantClient(path=settings.QDRANT_PATH)
    embedder = SentenceTransformer(settings.EMBEDDING_MODEL)

    query_vector = embedder.encode(query, normalize_embeddings=True).tolist()

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k
    ).points

    print(f"\n--- Search results for query: '{query}' (top {top_k}) ---")
    for idx, hit in enumerate(results, 1):
        payload = hit.payload
        print(f"\n[{idx}] Score: {hit.score:.4f}")
        print(f"    doc_id:       {payload.get('doc_id')}")
        print(f"    access_level: {payload.get('access_level')}")
        print(f"    title:        {payload.get('title')}")
        print(f"    section:      {payload.get('section')}")
        snippet = payload.get('text', '').replace('\n', ' ')[:120]
        print(f"    snippet:      {snippet}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug search across all documents without RBAC.")
    parser.add_argument("query", type=str, help="Search query string")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    args = parser.parse_args()

    search_debug(args.query, top_k=args.top_k)
