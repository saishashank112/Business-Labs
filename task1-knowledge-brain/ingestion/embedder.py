"""ChromaDB vector store and embedding integration.

Uses ChromaDB persistent storage and sentence-transformers / onnx embeddings.
"""

from __future__ import annotations

import json
import logging
from typing import List, Dict, Any, Optional

from app.config import settings
from app.models import Chunk

logger = logging.getLogger(__name__)

# Cache the chroma collection instance
_collection = None


def get_collection():
    """Get or create the ChromaDB collection for knowledge chunks."""
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    from chromadb.config import Settings as ChromaSettings

    client = chromadb.PersistentClient(
        path=settings.t1_chroma_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    # Use default embedding function or sentence-transformer if configured
    try:
        from chromadb.utils import embedding_functions
        ef = embedding_functions.DefaultEmbeddingFunction()
    except Exception as e:
        logger.warning("Could not load default embedding function: %s", e)
        ef = None

    _collection = client.get_or_create_collection(
        name="knowledge_chunks",
        embedding_function=ef,
        metadata={"description": "Brilliant Directories documentation chunks"},
    )
    return _collection


def upsert_chunks_vector(chunks: list[Chunk]) -> None:
    """Upsert chunks into ChromaDB collection."""
    if not chunks:
        return

    collection = get_collection()

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for chunk in chunks:
        ids.append(chunk.chunk_id)
        documents.append(chunk.content)
        metadatas.append({
            "article_id": chunk.article_id,
            "url": chunk.url,
            "title": chunk.title,
            "heading": chunk.heading,
            "image_refs": json.dumps(chunk.image_refs),
            "chunk_index": chunk.chunk_index,
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )
    logger.info("Upserted %d chunks into ChromaDB", len(chunks))


def search_vector(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Query ChromaDB for semantically similar chunks.
    
    Returns list of dicts:
        {
            "chunk_id": str,
            "article_id": str,
            "url": str,
            "title": str,
            "heading": str,
            "content": str,
            "score": float,  # Similarity score 0.0 - 1.0 (higher is better)
            "image_refs": list[str]
        }
    """
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    actual_k = min(top_k, count)
    results = collection.query(
        query_texts=[query],
        n_results=actual_k,
    )

    formatted: list[dict[str, Any]] = []
    if not results or not results.get("ids") or not results["ids"][0]:
        return formatted

    ids = results["ids"][0]
    docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
    metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
    distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

    for c_id, doc, meta, dist in zip(ids, docs, metadatas, distances):
        # Convert cosine distance or L2 distance to similarity score
        # For cosine/L2 distance, smaller is closer.
        score = max(0.0, min(1.0, 1.0 - (dist / 2.0))) if dist is not None else 0.5
        
        raw_images = meta.get("image_refs", "[]")
        try:
            image_refs = json.loads(raw_images) if isinstance(raw_images, str) else []
        except Exception:
            image_refs = []

        formatted.append({
            "chunk_id": c_id,
            "article_id": meta.get("article_id", ""),
            "url": meta.get("url", ""),
            "title": meta.get("title", ""),
            "heading": meta.get("heading", ""),
            "content": doc,
            "score": round(score, 4),
            "image_refs": image_refs,
        })

    return formatted
