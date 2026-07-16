"""Caso de uso canónico #1: responder preguntas con citas (doc 08, Sprint 4).

En Fase 1 el "planner" es un pipeline FIJO de dos pasos (retrieval → síntesis),
pero cada paso se envuelve en los contratos de agentes (`AgentRequest`/
`AgentResponse`) para que la Fase 4 lo sustituya por un planner real sin cambiar
el contrato (doc 03 §6). Regla de oro (doc 06 §2): una respuesta sin evidencia
real solo es válida si declara explícitamente que no encontró nada.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.llm.base import EmbeddingClient, LLMClient
from kos_core.schemas import AgentRequest, AgentResponse, Constraints, Cost, EvidenceRef
from kos_core.storage import search as search_storage
from kos_core.storage.search import SearchHit

_SYSTEM_PROMPT = (
    "Eres KOS, un asistente que responde SOLO con la evidencia numerada que se te "
    "proporciona. Reglas estrictas:\n"
    "1. Responde en el mismo idioma que la pregunta.\n"
    "2. Cita cada afirmación con el marcador correspondiente entre corchetes, p. ej. [1].\n"
    "3. Usa TODA la evidencia relevante, aunque sea parcial o indirecta: si un fragmento "
    "menciona o describe algo relacionado con la pregunta, es información válida para "
    "responder con ella, incluso si no responde el 100% de la pregunta.\n"
    "4. Solo declara que no hay evidencia si NINGÚN fragmento se relaciona con la "
    "pregunta. Si la evidencia es parcial, responde con lo que sí cubre y aclara "
    "explícitamente qué falta — nunca te niegues a responder cuando hay evidencia "
    "relacionada disponible.\n"
    "5. No uses conocimiento externo a la evidencia: no inventes hechos que no estén en "
    "ella, pero sí puedes conectar/resumir lo que varios fragmentos dicen en conjunto."
)

_NO_EVIDENCE_ANSWER = (
    "No encontré evidencia en la base de conocimiento para responder a esa pregunta."
)


class SynthesisError(Exception):
    """El LLM de síntesis (s2) no pudo generar la respuesta. La ruta la mapea a 503;
    los fallos de retrieval (s1) NO son esto y suben como 500 genérico."""


class PlanStep(BaseModel):
    """Un paso del plan (fijo en Fase 1); la unidad de traza y depuración (doc 03 §3)."""

    id: str
    agent: str
    task: str
    depends_on: list[str] = Field(default_factory=list)
    evidence_count: int | None = None


class QueryResult(BaseModel):
    answer: str
    evidence: list[EvidenceRef]
    confidence: float
    plan: list[PlanStep]
    degraded: bool = False
    cost: Cost = Field(default_factory=Cost)


def _evidence_from_hit(hit: SearchHit) -> EvidenceRef:
    return EvidenceRef(
        doc_id=hit.doc_id,
        chunk_id=hit.chunk_id,
        quote=hit.text,
        title=hit.title,
        source_id=hit.source_id,
        connector=hit.connector,
        score=hit.score,
    )


def _confidence_from_hits(hits: list[SearchHit], mode: str) -> float:
    """Confianza heurística honesta a partir del mejor hit (doc 06 §2).

    En modo hybrid el score es una fusión RRF (doc 08, Sprint 3): por diseño
    está acotado a ~1/(RRF_K + 1) por ranking fusionado (2: léxico + vector),
    así que el valor crudo nunca se acerca a 1.0 aunque el match sea perfecto.
    Normalizamos contra ese máximo teórico para que la confianza recorra
    [0, 1] de verdad. En lexical/vector el score ya viene aprox. en [0, 1].
    """
    if not hits:
        return 0.0
    top_score = hits[0].score
    if mode == "hybrid":
        max_possible = 2.0 / (search_storage.RRF_K + 1)
        return max(0.0, min(1.0, top_score / max_possible))
    return max(0.0, min(1.0, top_score))


async def _retrieve(
    engine: AsyncEngine,
    embedder: EmbeddingClient,
    *,
    query: str,
    limit: int,
    mode: str,
    trace_id: str,
) -> tuple[AgentResponse, bool]:
    """Paso s1: recupera evidencia. Devuelve (AgentResponse, degraded).

    En modo hybrid/vector embebe la query; si Ollama de embeddings falla, degrada
    a búsqueda léxica pura (doc 06: la evidencia manda, mejor léxica que nada).
    """
    degraded = False
    effective_mode = mode
    hits: list[SearchHit]
    if mode == "lexical":
        hits = await search_storage.lexical_search(engine, query, limit=limit)
    else:
        try:
            [query_embedding] = await embedder.embed([query])
        except Exception:
            hits = await search_storage.lexical_search(engine, query, limit=limit)
            degraded = True
            effective_mode = "lexical"
        else:
            if mode == "vector":
                hits = await search_storage.vector_search(engine, query_embedding, limit=limit)
            else:
                hits = await search_storage.hybrid_search(
                    engine, query, query_embedding, limit=limit
                )

    evidence = [_evidence_from_hit(hit) for hit in hits]
    # Confianza: heurística honesta a partir del mejor hit, normalizada al modo
    # efectivo de retrieval (no el solicitado, si hubo degradación a léxica).
    confidence = _confidence_from_hits(hits, effective_mode)
    response = AgentResponse(
        outputs={"hit_count": len(hits)},
        evidence=evidence,
        confidence=confidence,
        trace_id=trace_id,
    )
    return response, degraded


def _build_context(evidence: list[EvidenceRef]) -> str:
    bloques = []
    for index, ref in enumerate(evidence, start=1):
        titulo = ref.title or ref.source_id or "sin título"
        bloques.append(f"[{index}] ({titulo}) {ref.quote}")
    return "\n\n".join(bloques)


async def answer_query(
    *,
    engine: AsyncEngine,
    embedder: EmbeddingClient,
    llm: LLMClient,
    query: str,
    limit: int,
    trace_id: str,
    mode: str = "hybrid",
) -> QueryResult:
    """Pipeline fijo: retrieval (s1) → síntesis con citas (s2)."""
    started = time.perf_counter()

    retrieval_request = AgentRequest(
        task="retrieval",
        inputs={"query": query, "mode": mode, "limit": limit},
        constraints=Constraints(),
        trace_id=trace_id,
    )
    retrieval, degraded = await _retrieve(
        engine, embedder, query=query, limit=limit, mode=mode, trace_id=trace_id
    )
    _ = retrieval_request  # el contrato de entrada existe para el refactor a Fase 4
    evidence = retrieval.evidence

    plan = [
        PlanStep(
            id="s1",
            agent="retrieval",
            task=f"buscar evidencia para: {query}",
            evidence_count=len(evidence),
        ),
        PlanStep(
            id="s2",
            agent="writing",
            task="redactar la respuesta con citas a partir de la evidencia",
            depends_on=["s1"],
        ),
    ]

    if not evidence:
        # Sin evidencia no se llama al LLM: no se permite alucinar (doc 06 §2).
        elapsed_ms = (time.perf_counter() - started) * 1000
        return QueryResult(
            answer=_NO_EVIDENCE_ANSWER,
            evidence=[],
            confidence=0.0,
            plan=plan,
            degraded=degraded,
            cost=Cost(ms=elapsed_ms),
        )

    context = _build_context(evidence)
    prompt = (
        f"Pregunta: {query}\n\n"
        f"Evidencia disponible:\n{context}\n\n"
        "Responde a la pregunta usando solo la evidencia anterior y citando con [n]."
    )
    try:
        answer = await llm.generate(prompt, system=_SYSTEM_PROMPT)
    except Exception as exc:  # solo la síntesis; retrieval ya terminó
        raise SynthesisError(str(exc)) from exc

    elapsed_ms = (time.perf_counter() - started) * 1000
    return QueryResult(
        answer=answer,
        evidence=evidence,
        confidence=retrieval.confidence,
        plan=plan,
        degraded=degraded,
        cost=Cost(ms=elapsed_ms),
    )
