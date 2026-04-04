"""
Step 2: Brand Memory
ChromaDB-based RAG for brand context retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb

from backend.config import settings

logger = logging.getLogger(__name__)

_client: chromadb.HttpClient | None = None


def _get_client() -> chromadb.HttpClient:
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.chroma_host, port=settings.chroma_port
        )
    return _client


def _chunk_markdown(text: str, max_chars: int = 1500) -> list[str]:
    """Split markdown by ## headings, respecting max chunk size."""
    sections = text.split("\n## ")
    chunks = []

    for i, section in enumerate(sections):
        if i > 0:
            section = "## " + section
        # Split further if too long
        if len(section) > max_chars:
            lines = section.split("\n")
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 > max_chars and current:
                    chunks.append(current.strip())
                    current = line + "\n"
                else:
                    current += line + "\n"
            if current.strip():
                chunks.append(current.strip())
        elif section.strip():
            chunks.append(section.strip())

    return chunks


async def ingest_brand(brand_id: str, brand_dir: Path) -> int:
    """Ingest all .md files from a brand directory into ChromaDB.

    Returns the number of chunks ingested.
    """
    client = _get_client()

    # Delete existing collection if any
    try:
        client.delete_collection(name=brand_id)
    except Exception:
        pass

    collection = client.get_or_create_collection(name=brand_id)

    all_chunks: list[str] = []
    all_ids: list[str] = []
    all_metadata: list[dict] = []

    for md_file in brand_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        chunks = _chunk_markdown(text)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{brand_id}_{md_file.stem}_{i}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metadata.append({"source": md_file.name, "brand_id": brand_id})

    if all_chunks:
        collection.add(
            documents=all_chunks,
            ids=all_ids,
            metadatas=all_metadata,
        )
        logger.info(f"Ingested {len(all_chunks)} chunks for brand '{brand_id}'")

    return len(all_chunks)


async def query_brand_context(
    brand_id: str, query: str, n_results: int = 10
) -> str:
    """Query ChromaDB for relevant brand context.

    Returns concatenated relevant chunks as a single string.
    """
    client = _get_client()

    try:
        collection = client.get_collection(name=brand_id)
    except Exception:
        logger.warning(f"No ChromaDB collection found for brand '{brand_id}'")
        return ""

    results = collection.query(query_texts=[query], n_results=n_results)

    if not results["documents"] or not results["documents"][0]:
        return ""

    return "\n\n---\n\n".join(results["documents"][0])


async def check_health() -> bool:
    """Check if ChromaDB is reachable."""
    try:
        client = _get_client()
        client.heartbeat()
        return True
    except Exception:
        return False
