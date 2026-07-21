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

from kos_api.deps import postgres_engine, settings_dep
from kos_api.services import notes_service, query_service
from kos_core.config import Settings
from kos_core.schemas import EvidenceRef

router = APIRouter(prefix="/v1/query", tags=["query"])

QueryMode = Literal["hybrid", "lexical", "vector"]

# Comando explícito de creación de notas (doc 06 §4, versión directa en la API):
# el usuario tecleándolo él mismo ya es la aprobación que pide esa regla.
_NUEVA_MAQUINA_PREFIX = "/nueva-maquina "
_HTB_TEMPLATE = "MaquinaHTB"
_HTB_FOLDER = "Security/HackTheBox/Máquinas"


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


async def _handle_nueva_maquina(
    name: str, *, engine: AsyncEngine, settings: Settings, trace_id: str
) -> QueryResponse:
    """Comando `/nueva-maquina <nombre>`: crea la nota sin pasar por retrieval/síntesis."""
    try:
        vault_path = await notes_service.get_vault_path(engine, settings.kos_default_vault_source)
        note_path = notes_service.create_note(
            vault_path, template_name=_HTB_TEMPLATE, folder=_HTB_FOLDER, title=name
        )
    except notes_service.NoteAlreadyExistsError as exc:
        answer = f"⚠️ {exc}"
    except (notes_service.VaultSourceNotFoundError, notes_service.TemplateNotFoundError) as exc:
        answer = f"❌ {exc}"
    else:
        answer = f"✅ Nota creada: {note_path}"
    return QueryResponse(
        query=f"{_NUEVA_MAQUINA_PREFIX}{name}",
        answer=answer,
        evidence=[],
        confidence=1.0,
        plan=[
            query_service.PlanStep(id="s0", agent="notes", task="crear nota desde plantilla"),
        ],
        degraded=False,
        trace_id=trace_id,
    )


@router.post("", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    request: Request,
    engine: AsyncEngine = Depends(postgres_engine),
    settings: Settings = Depends(settings_dep),
) -> QueryResponse:
    trace_id: str = getattr(request.state, "trace_id", str(uuid.uuid4()))

    stripped = body.query.strip()
    if stripped.startswith(_NUEVA_MAQUINA_PREFIX):
        name = stripped[len(_NUEVA_MAQUINA_PREFIX) :].strip()
        if name:
            return await _handle_nueva_maquina(
                name, engine=engine, settings=settings, trace_id=trace_id
            )

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
