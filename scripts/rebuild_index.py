from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.documents import build_chunks, load_documents
from app.embeddings import ollama_embed
from app.retrieval import build_vector_index


def main() -> None:
    settings = get_settings()
    documents = load_documents()
    chunks = build_chunks(documents, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    embeddings = ollama_embed(
        [chunk.text for chunk in chunks],
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
        timeout=settings.request_timeout,
    )
    index = build_vector_index(chunks, embeddings)
    index.save()
    print(json.dumps({"documents": len(documents), "chunks": len(chunks)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
