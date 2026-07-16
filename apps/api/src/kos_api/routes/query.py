"""POST /v1/query — pregunta → respuesta con citas (doc 06 §2, Sprint 4).

Es el caso de uso canónico #1: retrieval → síntesis LLM → respuesta con
`evidence[]`. Una respuesta sin evidencia real solo es válida si lo declara.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_api.services import query_service
from kos_core.schemas import EvidenceRef

router = APIRouter(prefix="/v1/query", tags=["query"])

QueryMode = Literal["hybrid", "lexical", "vector"]


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=20)
    mode: QueryMode = "hybrid"


class QueryResponse(BaseModel):
    query: str
    answer: str
    evidence: list[EvidenceRef]
    confidence: float
    plan: list[query_service.PlanStep]
    degraded: bool
    trace_id: str


@router.post("", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    request: Request,
    engine: AsyncEngine = Depends(postgres_engine),
) -> QueryResponse:
    trace_id: str = getattr(request.state, "trace_id", str(uuid.uuid4()))
    try:
        result = await query_service.answer_query(
            engine=engine,
            embedder=request.app.state.embedding_client,
            llm=request.app.state.llm_client,
            query=body.query,
            limit=body.limit,
            trace_id=trace_id,
            mode=body.mode,
        )
    except query_service.SynthesisError as exc:
        # Solo el fallo de síntesis es 503; un error de retrieval/BD sube a 500 (RFC 9457).
        raise HTTPException(status_code=503, detail="Síntesis no disponible (Ollama)") from exc

    return QueryResponse(
        query=body.query,
        answer=result.answer,
        evidence=result.evidence,
        confidence=result.confidence,
        plan=result.plan,
        degraded=result.degraded,
        trace_id=trace_id,
    )
