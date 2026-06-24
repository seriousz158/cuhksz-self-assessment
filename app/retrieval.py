from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from app.config import INDEX_DIR
from app.documents import Chunk


def tokenize(text: str) -> list[str]:
    return [token.strip().lower() for token in jieba.lcut(text) if token.strip()]


class VectorIndex:
    def __init__(self, vectors: np.ndarray, chunks: list[Chunk]) -> None:
        if vectors.ndim != 2:
            raise ValueError("vectors must be a 2D array")
        if len(vectors) != len(chunks):
            raise ValueError("vector count must match chunk count")
        # Row-wise L2 normalisation so cosine similarity reduces to a dot
        # product (the standard metric for bge-m3). Guard zero vectors so we
        # never divide by zero — a NaN here would silently corrupt argsort.
        row_norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        row_norms[row_norms == 0] = 1e-12
        self.vectors = (vectors / row_norms).astype("float32")
        self.chunks = chunks

    def search(self, query_vector: list[float], top_k: int = 10) -> list[dict[str, object]]:
        if not self.chunks:
            return []
        query = np.array(query_vector, dtype="float32")
        query_norm = float(np.linalg.norm(query)) or 1e-12
        query = query / query_norm
        similarities = self.vectors @ query
        order = np.argsort(similarities)[::-1][:top_k]
        return [
            {
                "rank": rank + 1,
                "score": float(similarities[index]),
                "distance": float(1 - similarities[index]),
                "chunk": self.chunks[int(index)],
            }
            for rank, index in enumerate(order)
        ]

    def save(self, index_dir: Path = INDEX_DIR) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "vectors.npy", self.vectors)
        (index_dir / "chunks.json").write_text(
            json.dumps([chunk.to_dict() for chunk in self.chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, index_dir: Path = INDEX_DIR) -> "VectorIndex | None":
        vectors_path = index_dir / "vectors.npy"
        chunks_path = index_dir / "chunks.json"
        if not vectors_path.exists() or not chunks_path.exists():
            return None
        vectors = np.load(vectors_path)
        raw_chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        chunks = [Chunk(**item) for item in raw_chunks]
        return cls(vectors=vectors, chunks=chunks)


class HybridRetriever:
    def __init__(self, index: VectorIndex) -> None:
        self.index = index
        corpus = [tokenize(chunk.text) for chunk in index.chunks]
        self.bm25 = BM25Okapi(corpus) if corpus else None

    def keyword_search(self, query: str, top_k: int = 10) -> list[dict[str, object]]:
        if not self.bm25 or not self.index.chunks:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        order = np.argsort(scores)[::-1][:top_k]
        return [
            {
                "rank": rank + 1,
                "score": float(scores[index]),
                "chunk": self.index.chunks[int(index)],
            }
            for rank, index in enumerate(order)
            if scores[index] > 0
        ]

    def search(
        self,
        query: str,
        query_vector: list[float],
        top_k: int = 10,
        pool_multiplier: int = 2,
    ) -> list[dict[str, object]]:
        pool_k = max(top_k, top_k * pool_multiplier)
        vector_results = self.index.search(query_vector, top_k=pool_k)
        keyword_results = self.keyword_search(query, top_k=pool_k)
        return reciprocal_rank_fusion([vector_results, keyword_results], top_k=top_k)


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[dict[str, object]]],
    top_k: int = 10,
    rrf_k: int = 60,
) -> list[dict[str, object]]:
    scores: dict[int, float] = {}
    chunks: dict[int, Chunk] = {}
    vector_scores: dict[int, float] = {}
    keyword_scores: dict[int, float] = {}

    for list_index, ranked in enumerate(ranked_lists):
        for rank, item in enumerate(ranked, start=1):
            chunk = item["chunk"]
            if not isinstance(chunk, Chunk):
                continue
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1 / (rrf_k + rank)
            chunks[chunk.chunk_id] = chunk
            if list_index == 0:
                vector_scores[chunk.chunk_id] = float(item.get("score", 0.0))
            else:
                keyword_scores[chunk.chunk_id] = float(item.get("score", 0.0))

    ordered = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:top_k]
    return [
        {
            "score": score,
            "vector_score": vector_scores.get(chunk_id, 0.0),
            "keyword_score": keyword_scores.get(chunk_id, 0.0),
            "chunk": chunks[chunk_id],
        }
        for chunk_id, score in ordered
    ]


def build_vector_index(chunks: list[Chunk], embeddings: list[list[float]]) -> VectorIndex:
    if not chunks:
        raise ValueError("No document chunks found. Run /api/ingest first or add Markdown files.")
    if len(chunks) != len(embeddings):
        raise ValueError("Chunk count and embedding count do not match.")
    return VectorIndex(vectors=np.array(embeddings, dtype="float32"), chunks=chunks)


def result_to_source(result: dict[str, object]) -> dict[str, object]:
    chunk = result["chunk"]
    if not isinstance(chunk, Chunk):
        raise TypeError("result chunk is not a Chunk")
    return {
        "title": chunk.title,
        "url": chunk.url,
        "category": chunk.category,
        "applicant_path": chunk.applicant_path,
        "score": round(float(result.get("score", 0.0)), 6),
        "text": chunk.text[:900],
    }
