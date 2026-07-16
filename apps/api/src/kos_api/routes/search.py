"""POST /v1/search — búsqueda híbrida cruda, sin síntesis LLM (doc 06 §2, Sprint 3)."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_core.storage import search as search_storage

router = APIRouter(prefix="/v1/search", tags=["search"])

SearchMode = Literal["hybrid", "lexical", "vector"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    mode: SearchMode = "hybrid"


class SearchHitOut(BaseModel):
    """Cada hit incluye la evidencia mínima {doc_id, chunk_id, quote} (doc 06 §2)."""

    doc_id: uuid.UUID
    chunk_id: uuid.UUID
    quote: str
    score: float
    source: str
    title: str | None
    connector: str | None
    source_id: str | None
    heading: str | None


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    degraded: bool = False
    hits: list[SearchHitOut]


def _to_out(hit: search_storage.SearchHit) -> SearchHitOut:
    return SearchHitOut(
        doc_id=hit.doc_id,
        chunk_id=hit.chunk_id,
        quote=hit.text,
        score=hit.score,
        source=hit.source,
        title=hit.title,
        connector=hit.connector,
        source_id=hit.source_id,
        heading=hit.heading,
    )


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    request: Request,
    engine: AsyncEngine = Depends(postgres_engine),
) -> SearchResponse:
    if body.mode == "lexical":
        hits = await search_storage.lexical_search(engine, body.query, limit=body.limit)
        return SearchResponse(query=body.query, mode=body.mode, hits=[_to_out(h) for h in hits])

    embedder = request.app.state.embedding_client
    try:
        [query_embedding] = await embedder.embed([body.query])
    except Exception as exc:
        if body.mode == "vector":
            raise HTTPException(
                status_code=503, detail="Embeddings no disponibles (Ollama)"
            ) from exc
        # hybrid degrada a léxica pura si Ollama no responde
        hits = await search_storage.lexical_search(engine, body.query, limit=body.limit)
        return SearchResponse(
            query=body.query, mode=body.mode, degraded=True, hits=[_to_out(h) for h in hits]
        )

    if body.mode == "vector":
        hits = await search_storage.vector_search(engine, query_embedding, limit=body.limit)
    else:
        hits = await search_storage.hybrid_search(
            engine, body.query, query_embedding, limit=body.limit
        )
    return SearchResponse(query=body.query, mode=body.mode, hits=[_to_out(h) for h in hits])
