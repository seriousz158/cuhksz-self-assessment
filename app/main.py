from __future__ import annotations

import functools
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.assessor import (
    build_retrieval_query,
    call_llm_for_report,
    history_record,
    insufficient_response,
    soft_missing_labels,
    validate_profile,
)
from app.config import BASE_DIR, get_settings
from app.documents import build_chunks, load_documents
from app.embeddings import ollama_embed
from app.history import append_history, clear_history_with_double_confirmation, read_history
from app.ingest import ingest_sources
from app.models import AssessRequest, AssessResponse, ClearHistoryRequest, StatusResponse
from app.retrieval import HybridRetriever, VectorIndex, build_vector_index, result_to_source


settings = get_settings()
vector_index: VectorIndex | None = None
retriever: HybridRetriever | None = None


def load_index_from_disk() -> None:
    global vector_index, retriever
    vector_index = VectorIndex.load()
    retriever = HybridRetriever(vector_index) if vector_index else None


@functools.lru_cache(maxsize=1)
def cached_documents():
    """Parse the knowledge base once and memoise it.

    The parsed Markdown never changes between ingests, so /api/status and index
    rebuilds can reuse the result instead of re-reading every file each call.
    `ingest_sources()` writes new files, so callers must `cache_clear()` after it.
    """
    return load_documents()


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_index_from_disk()
    yield


app = FastAPI(title="CUHK-Shenzhen Undergraduate Self-Assessment KB", lifespan=lifespan)


def rebuild_index() -> dict[str, int]:
    global vector_index, retriever
    documents = cached_documents()
    chunks = build_chunks(documents, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    texts = [chunk.text for chunk in chunks]
    embeddings = ollama_embed(
        texts,
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
        timeout=settings.request_timeout,
    )
    vector_index = build_vector_index(chunks, embeddings)
    vector_index.save()
    retriever = HybridRetriever(vector_index)
    return {"documents": len(documents), "chunks": len(chunks)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/status", response_model=StatusResponse)
def status() -> StatusResponse:
    documents = cached_documents()
    return StatusResponse(
        documents=len(documents),
        chunks=len(vector_index.chunks) if vector_index else 0,
        index_ready=bool(vector_index and retriever),
        llm_configured=settings.llm_configured,
        embedding_model=settings.embedding_model,
        model_name=settings.model_name,
    )


@app.post("/api/ingest")
def ingest() -> dict[str, object]:
    result = ingest_sources()
    # Source files on disk may have changed — drop the memoised parse.
    cached_documents.cache_clear()
    ingested = result["ingested"]
    failed = result["failed"]
    return {
        "ingested": len(ingested),
        "failed": len(failed),
        "sources": ingested,
        "failures": failed,
    }


@app.post("/api/rebuild")
def rebuild() -> dict[str, object]:
    try:
        result = rebuild_index()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", **result}


@app.post("/api/assess", response_model=AssessResponse)
def assess(request: AssessRequest) -> AssessResponse:
    if not retriever:
        raise HTTPException(status_code=400, detail="知识库索引还没有准备好。请先运行 /api/ingest，再运行 /api/rebuild。")

    profile = request.profile
    hard_missing = validate_profile(profile)
    soft_missing = soft_missing_labels(profile)

    if hard_missing:
        # Critical fields are missing — there's nothing useful to retrieve or
        # send to the LLM yet. Return early so we don't pay an Ollama embedding
        # round-trip plus a full retrieval for an unusable request.
        response = insufficient_response(profile, hard_missing, [])
    else:
        query = build_retrieval_query(profile)
        try:
            query_vector = ollama_embed(
                [query],
                base_url=settings.ollama_base_url,
                model=settings.embedding_model,
                timeout=settings.request_timeout,
            )[0]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        raw_results = retriever.search(query, query_vector, top_k=settings.retrieval_top_k)
        sources = [result_to_source(result) for result in raw_results]

        try:
            report = call_llm_for_report(profile, sources, settings)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        response = AssessResponse(status="ok", report=report, missing_fields=soft_missing)

    if request.save_history:
        append_history(history_record(profile, response))
    return response


@app.get("/api/history")
def history(limit: int = 50) -> dict[str, object]:
    return {"items": read_history(limit=limit)}


@app.post("/api/history/clear")
def clear_history(request: ClearHistoryRequest) -> dict[str, str]:
    return clear_history_with_double_confirmation(
        confirm_first=request.confirm_first,
        confirm_second=request.confirm_second,
        phrase=request.phrase,
    )


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
