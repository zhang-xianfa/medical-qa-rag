import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("HF_HUB_OFFLINE", "1")

from knowledge.kb_loader import load_from_dicts
from knowledge.vector_store import get_vector_store
from knowledge.retriever import EmbeddingEncoder


async def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not input_file:
        print("Usage: python load_knowledge.py <input.json>")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        entries = json.load(f)

    loaded = load_from_dicts(entries)
    print(f"Loaded {len(loaded)} entries (skipped {len(entries) - len(loaded)} duplicates/invalid)")

    print("Generating embeddings with BGE-M3...")
    encoder = EmbeddingEncoder()
    texts = [e["content"][:512] for e in loaded]
    vectors = await encoder.encode(texts)
    print(f"Generated {len(vectors)} vectors, dim={len(vectors[0]) if vectors else 0}")

    store = get_vector_store()
    metadata = [
        {"knowledge_entry_id": e.get("content_hash", ""), "title": e.get("title", ""),
         "content": e.get("content", ""), "source": e.get("source", ""),
         "source_type": e.get("source_type", ""), "authority_score": e.get("authority_score", 0.5),
         "freshness_score": e.get("freshness_score", 1.0), "publish_year": e.get("publish_year", 2026)}
        for e in loaded
    ]
    ids = await store.insert(vectors, metadata)
    print(f"Inserted {len(ids)} vectors into vector store.")


if __name__ == "__main__":
    asyncio.run(main())
