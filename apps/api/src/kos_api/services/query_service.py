"""Caso de uso canónico #1: responder preguntas con citas (doc 08, Sprint 4).

En Fase 1 el "planner" es un pipeline FIJO de dos pasos (retrieval → síntesis),
pero cada paso se envuelve en los contratos de agentes (`AgentRequest`/
`AgentResponse`) para que la Fase 4 lo sustituya por un planner real sin cambiar
el contrato (doc 03 §6). Regla de oro (doc 06 §2): una respuesta sin evidencia
real solo es válida si declara explícitamente que no encontró nada.

Sprint 17: el paso de retrieval (s1) ya no llama `kos_core.storage.search`
directo — lo hace `RetrievalAgent` (`packages/agents`) vía la herramienta MCP
`vector.search` (ADR-0005). El `AgentRequest` que antes se construía y se
descartaba (`_ = retrieval_request`) ahora es el input real del agente.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from kos_agents.base import Agent
from kos_core.llm.base import LLMClient
from kos_core.schemas import AgentRequest, Constraints, Cost, EvidenceRef

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
    "ella, pero sí puedes conectar/resumir lo que varios fragmentos dicen en conjunto.\n"
    "6. Si la pregunta pide una plantilla o estructura para crear algo: si algún fragmento "
    "de evidencia está marcado como (plantilla), cítalo tal cual existe — no lo combines "
    "con fragmentos marcados como (nota) para 'completarlo' o inventar secciones que no "
    "están en él. Si ningún fragmento es una plantilla, dilo explícitamente ('no encontré "
    "una plantilla existente para esto') en vez de construir una a partir de fragmentos "
    "sueltos.\n"
    "7. Nunca presentes como una sola entidad coherente (una plantilla, un proceso, una "
    "definición) contenido que proviene de documentos distintos y no relacionados entre "
    "sí: cada fragmento se cita por separado, con su propia fuente; no fusiones "
    "estructuras de fuentes distintas."
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


def _build_context(evidence: list[EvidenceRef]) -> str:
    bloques = []
    for index, ref in enumerate(evidence, start=1):
        titulo = ref.title or ref.source_id or "sin título"
        tipo = "plantilla" if ref.doc_type == "template" else "nota"
        bloques.append(f"[{index}] ({titulo} · {tipo}) {ref.quote}")
    return "\n\n".join(bloques)


async def answer_query(
    *,
    retrieval_agent: Agent,
    llm: LLMClient,
    query: str,
    limit: int,
    trace_id: str,
    mode: str = "hybrid",
) -> QueryResult:
    """Pipeline fijo: retrieval (s1, vía `RetrievalAgent`/MCP) → síntesis con citas (s2)."""
    started = time.perf_counter()

    retrieval_request = AgentRequest(
        task="retrieval",
        inputs={"query": query, "mode": mode, "limit": limit},
        constraints=Constraints(),
        trace_id=trace_id,
    )
    retrieval = await retrieval_agent(retrieval_request)
    degraded = bool(retrieval.outputs.get("degraded", False))
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
