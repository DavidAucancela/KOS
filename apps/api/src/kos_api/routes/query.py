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

from kos_agents.graph import GraphAgent
from kos_agents.memory import MemoryAgent
from kos_agents.planner.planner import Planner
from kos_agents.research import ResearchAgent
from kos_agents.retrieval import RetrievalAgent
from kos_agents.writing import WritingAgent
from kos_api.deps import postgres_engine, settings_dep, tool_caller
from kos_api.services import memory_service, notes_service, query_service, template_intent_service
from kos_api.services.intent_service import detect_template_intent
from kos_core.config import Settings
from kos_core.schemas import EvidenceRef
from kos_mcp.client import EmbeddedToolCaller

router = APIRouter(prefix="/v1/query", tags=["query"])

QueryMode = Literal["hybrid", "lexical", "vector"]

# Comandos explícitos de creación de notas (doc 06 §4, versión directa en la API):
# el usuario tecleándolo él mismo ya es la aprobación que pide esa regla.
_CREAR_NOTA_PREFIX = "/crear-nota "
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
    plan_id: str


async def _handle_crear_nota(
    *,
    template_name: str,
    folder: str,
    title: str,
    original_query: str,
    engine: AsyncEngine,
    settings: Settings,
    trace_id: str,
) -> QueryResponse:
    """Comando `/crear-nota <template>|<folder>|<título>`: crea la nota sin pasar
    por retrieval/síntesis. Generalización de `/nueva-maquina` (Sprint 7 → 8)."""
    try:
        vault_path = await notes_service.get_vault_path(engine, settings.kos_default_vault_source)
        note_path = notes_service.create_note(
            vault_path, template_name=template_name, folder=folder, title=title
        )
    except notes_service.NoteAlreadyExistsError as exc:
        answer = f"⚠️ {exc}"
    except (notes_service.VaultSourceNotFoundError, notes_service.TemplateNotFoundError) as exc:
        answer = f"❌ {exc}"
    else:
        answer = f"✅ Nota creada: {note_path}"
    return QueryResponse(
        query=original_query,
        answer=answer,
        evidence=[],
        confidence=1.0,
        plan=[
            query_service.PlanStep(id="s0", agent="notes", task="crear nota desde plantilla"),
        ],
        degraded=False,
        trace_id=trace_id,
        # Sintético: este comando no pasa por el Planner real, no hay fila en
        # `plans` que consultar vía GET /v1/plans/{id} para este id.
        plan_id=str(uuid.uuid4()),
    )


def _parse_crear_nota_args(raw: str) -> tuple[str, str, str] | None:
    """Parsea `<template>|<folder>|<título>`; None si falta algún segmento."""
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) != 3 or not all(parts):
        return None
    template_name, folder, title = parts
    return template_name, folder, title


@router.post("", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    request: Request,
    engine: AsyncEngine = Depends(postgres_engine),
    settings: Settings = Depends(settings_dep),
    caller: EmbeddedToolCaller = Depends(tool_caller),
) -> QueryResponse:
    trace_id: str = getattr(request.state, "trace_id", str(uuid.uuid4()))

    stripped = body.query.strip()
    if stripped.startswith(_NUEVA_MAQUINA_PREFIX):
        name = stripped[len(_NUEVA_MAQUINA_PREFIX) :].strip()
        if name:
            return await _handle_crear_nota(
                template_name=_HTB_TEMPLATE,
                folder=_HTB_FOLDER,
                title=name,
                original_query=body.query,
                engine=engine,
                settings=settings,
                trace_id=trace_id,
            )
    if stripped.startswith(_CREAR_NOTA_PREFIX):
        args = _parse_crear_nota_args(stripped[len(_CREAR_NOTA_PREFIX) :])
        if args is not None:
            template_name, folder, title = args
            return await _handle_crear_nota(
                template_name=template_name,
                folder=folder,
                title=title,
                original_query=body.query,
                engine=engine,
                settings=settings,
                trace_id=trace_id,
            )

    if detect_template_intent(body.query):
        result = await template_intent_service.resolve_template_intent(
            engine,
            request.app.state.embedding_client,
            query=body.query,
            trace_id=trace_id,
        )
        return QueryResponse(
            query=body.query,
            answer=result.answer,
            evidence=result.evidence,
            confidence=result.confidence,
            plan=result.plan,
            degraded=result.degraded,
            trace_id=trace_id,
            # Sintético (generado en template_intent_service): la rama s0 no
            # pasa por el Planner real, no hay fila en `plans` para este id.
            plan_id=result.plan_id,
        )

    planner = Planner(
        llm=request.app.state.llm_client,
        retrieval_agent=RetrievalAgent(caller),
        graph_agent=GraphAgent(caller),
        research_agent=ResearchAgent(caller),
        memory_agent=MemoryAgent(caller),
        writing_agent=WritingAgent(request.app.state.llm_client),
    )
    try:
        result = await query_service.answer_query(
            planner=planner,
            query=body.query,
            limit=body.limit,
            trace_id=trace_id,
            engine=engine,
            mode=body.mode,
        )
    except query_service.SynthesisError as exc:
        # Solo el fallo de síntesis es 503; un error de retrieval/BD sube a 500 (RFC 9457).
        raise HTTPException(status_code=503, detail="Síntesis no disponible (Ollama)") from exc

    # Memoria episódica (doc 04 §3 paso 1, Sprint 12): encolada sin bloquear la
    # respuesta ("la UI nunca espera al aprendizaje"). Solo el pipeline de
    # pregunta/respuesta — los comandos (/crear-nota, /nueva-maquina) no pasan
    # por acá, son acciones, no preguntas.
    memory_service.enqueue_learn(
        settings,
        query=body.query,
        answer=result.answer,
        sources=sorted({str(ev.doc_id) for ev in result.evidence}),
        confidence=result.confidence,
    )

    return QueryResponse(
        query=body.query,
        answer=result.answer,
        evidence=result.evidence,
        confidence=result.confidence,
        plan=result.plan,
        degraded=result.degraded,
        trace_id=trace_id,
        plan_id=result.plan_id,
    )
