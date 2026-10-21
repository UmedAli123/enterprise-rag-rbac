"""Document loading, heading-aware chunking, embedding, and vector database ingestion."""

import argparse
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List

import frontmatter
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

COLLECTION_NAME = "nexora_docs"
REQUIRED_FIELDS = ["doc_id", "access_level", "department", "last_updated"]
VALID_ACCESS_LEVELS = {"public", "hr", "finance", "engineering", "executive"}

# Namespace for deterministic chunk UUID5 generation
NAMESPACE_CHUNKS = uuid.UUID("a9e223bf-f5b2-4d2b-b6d8-77c8e9d3d3a0")


def generate_chunk_uuid(chunk_id: str) -> str:
    """Generate a deterministic UUID string from chunk_id."""
    return str(uuid.uuid5(NAMESPACE_CHUNKS, chunk_id))


def parse_markdown_file(file_path: Path) -> Dict[str, Any] | None:
    """Parse YAML frontmatter and content from markdown file.
    
    Returns None if any required frontmatter field is missing.
    """
    try:
        post = frontmatter.load(str(file_path))
    except Exception as e:
        logger.warning("Failed to parse YAML frontmatter for %s: %s", file_path, e)
        return None

    metadata = post.metadata
    for field in REQUIRED_FIELDS:
        if field not in metadata or not metadata[field]:
            logger.warning("Skipping %s: missing required field '%s'", file_path, field)
            return None

    return {
        "metadata": metadata,
        "content": post.content,
        "source_path": str(file_path.relative_to(Path(settings.DATA_DIR).parent) if Path(settings.DATA_DIR).parent in file_path.parents else file_path)
    }


def split_document_by_headings(content: str, metadata: Dict[str, Any], source_path: str) -> List[Dict[str, Any]]:
    """Split markdown document into chunks by headings (## and ###).
    
    Target: 500-800 tokens (approx 2000-3200 characters) with overlap.
    Preserves tables intact (never splits a table row).
    Extracts H1 as doc title and nearest heading as section.
    """
    lines = content.split("\n")
    h1_title = metadata.get("title", "")
    
    # Locate H1 if not explicitly in metadata
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            h1_title = line.lstrip("# ").strip()
            break
            
    if not h1_title:
        h1_title = metadata.get("doc_id", "Document")

    # Split into sections by ## and ###
    sections: List[Dict[str, Any]] = []
    current_heading = "Overview"
    current_lines: List[str] = []

    for line in lines:
        # Detect headings
        if re.match(r"^#{2,3}\s+", line):
            if current_lines:
                text_block = "\n".join(current_lines).strip()
                if text_block:
                    sections.append({
                        "section": current_heading,
                        "text": text_block
                    })
                current_lines = []
            current_heading = re.sub(r"^#{2,3}\s+", "", line).strip()
        else:
            current_lines.append(line)

    if current_lines:
        text_block = "\n".join(current_lines).strip()
        if text_block:
            sections.append({
                "section": current_heading,
                "text": text_block
            })

    # Sub-chunk sections if necessary while keeping tables intact
    chunks: List[Dict[str, Any]] = []
    chunk_index = 0

    for sec in sections:
        sec_name = sec["section"]
        sec_text = sec["text"]
        
        # Approximate token count by word count
        words = sec_text.split()
        if len(words) <= 700:
            chunk_id = f"{metadata['doc_id']}-{chunk_index:02d}"
            chunks.append({
                "chunk_id": chunk_id,
                "doc_id": metadata["doc_id"],
                "access_level": str(metadata["access_level"]).lower(),
                "department": metadata["department"],
                "title": h1_title,
                "section": sec_name,
                "last_updated": str(metadata["last_updated"]),
                "source_path": source_path,
                "text": sec_text
            })
            chunk_index += 1
        else:
            # Split section safely (avoid splitting markdown tables)
            sec_lines = sec_text.split("\n")
            buffer_lines: List[str] = []
            in_table = False
            
            for line in sec_lines:
                if line.strip().startswith("|") and line.strip().endswith("|"):
                    in_table = True
                else:
                    in_table = False

                buffer_lines.append(line)
                approx_words = sum(len(l.split()) for l in buffer_lines)

                # Split if chunk is big enough and not inside a table
                if approx_words >= 600 and not in_table:
                    chunk_id = f"{metadata['doc_id']}-{chunk_index:02d}"
                    chunks.append({
                        "chunk_id": chunk_id,
                        "doc_id": metadata["doc_id"],
                        "access_level": str(metadata["access_level"]).lower(),
                        "department": metadata["department"],
                        "title": h1_title,
                        "section": sec_name,
                        "last_updated": str(metadata["last_updated"]),
                        "source_path": source_path,
                        "text": "\n".join(buffer_lines).strip()
                    })
                    chunk_index += 1
                    # 80-100 token overlap (~60 words from previous buffer)
                    overlap_words: List[str] = []
                    overlap_lines: List[str] = []
                    for prev_line in reversed(buffer_lines):
                        w = prev_line.split()
                        overlap_words.extend(w)
                        overlap_lines.insert(0, prev_line)
                        if len(overlap_words) >= 80:
                            break
                    buffer_lines = overlap_lines

            if buffer_lines:
                chunk_id = f"{metadata['doc_id']}-{chunk_index:02d}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "doc_id": metadata["doc_id"],
                    "access_level": str(metadata["access_level"]).lower(),
                    "department": metadata["department"],
                    "title": h1_title,
                    "section": sec_name,
                    "last_updated": str(metadata["last_updated"]),
                    "source_path": source_path,
                    "text": "\n".join(buffer_lines).strip()
                })
                chunk_index += 1

    return chunks


def load_and_chunk_documents(docs_dir: Path) -> List[Dict[str, Any]]:
    """Recursively load all .md documents and chunk them."""
    all_chunks: List[Dict[str, Any]] = []
    md_files = sorted(list(docs_dir.rglob("*.md")))

    for md_file in md_files:
        # Skip README or non-doc files if any
        if md_file.name == "README.md":
            continue

        parsed = parse_markdown_file(md_file)
        if not parsed:
            continue

        chunks = split_document_by_headings(
            content=parsed["content"],
            metadata=parsed["metadata"],
            source_path=parsed["source_path"]
        )
        all_chunks.extend(chunks)

    return all_chunks


def ingest(reset: bool = False) -> int:
    """Run ingestion pipeline: load, chunk, embed, and store in local embedded Qdrant."""
    docs_path = Path(settings.DATA_DIR) / "nexora_docs"
    if not docs_path.exists():
        docs_path = Path("./data/nexora_docs")

    logger.info("Loading documents from: %s", docs_path)
    chunks = load_and_chunk_documents(docs_path)
    logger.info("Generated %d chunks from documents", len(chunks))

    if not chunks:
        logger.warning("No chunks generated. Exiting.")
        return 0

    # Initialize Qdrant Client (local embedded storage)
    client = QdrantClient(path=settings.QDRANT_PATH)

    # Check / recreate collection
    existing_collections = [c.name for c in client.get_collections().collections]
    
    if reset and COLLECTION_NAME in existing_collections:
        logger.info("Resetting collection '%s'", COLLECTION_NAME)
        client.delete_collection(COLLECTION_NAME)
        existing_collections.remove(COLLECTION_NAME)

    # Initialize Embedding model
    logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
    embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
    vector_size = embedder.get_sentence_embedding_dimension()

    if COLLECTION_NAME not in existing_collections:
        logger.info("Creating Qdrant collection '%s' with vector size %d", COLLECTION_NAME, vector_size)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE
            )
        )
        # Create payload index on access_level for pre-filtering
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="access_level",
            field_schema=models.PayloadSchemaType.KEYWORD
        )

    # Embed and prepare points
    logger.info("Embedding %d chunks with normalization...", len(chunks))
    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    points = []
    for chunk, emb in zip(chunks, embeddings):
        point_id = generate_chunk_uuid(chunk["chunk_id"])
        points.append(
            models.PointStruct(
                id=point_id,
                vector=emb.tolist(),
                payload=chunk
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True
    )
    
    count_info = client.count(collection_name=COLLECTION_NAME)
    total_count = count_info.count
    client.close()
    logger.info("Ingestion completed successfully. Total points in collection: %d", total_count)
    return total_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Nexora documents into Qdrant vector database.")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the collection before ingestion.")
    args = parser.parse_args()
    ingest(reset=args.reset)
