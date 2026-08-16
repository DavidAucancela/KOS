"""Caso de uso canónico #1: responder preguntas con citas (doc 08, Sprint 4).

Sprint 18: el pipeline fijo de 2 pasos ya no vive acá — `answer_query` es un
wrapper delgado sobre `Planner` (`packages/agents`), que decide entre un plan
dinámico (LLM elige retrieval/graph/writing) o el plan fijo retrieval→writing
como red de seguridad (doc 03 §3 regla 4). La forma de `QueryResult` no
cambia: sigue siendo lo que `routes/query.py` traduce 1:1 a `QueryResponse`.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from kos_agents.planner.planner import Planner
from kos_agents.writing import SynthesisError as WritingSynthesisError
from kos_core.schemas import Cost, EvidenceRef, PlanStep
from kos_core.schemas.plan import PlanRequest

# Reexportados para no romper los call sites existentes
# (`apps/api/.../template_intent_service.py`, `routes/query.py`) que ya
# importan `PlanStep`/`Cost` desde este módulo.
__all__ = ["Cost", "PlanStep", "QueryResult", "SynthesisError", "answer_query"]


class SynthesisError(Exception):
    """El paso de síntesis (`WritingAgent`) no pudo generar la respuesta. La
    ruta la mapea a 503; fallos de los pasos previos suben como 500 genérico."""


class QueryResult(BaseModel):
    answer: str
    evidence: list[EvidenceRef]
    confidence: float
    plan: list[PlanStep]
    degraded: bool = False
    cost: Cost = Field(default_factory=Cost)


async def answer_query(
    *,
    planner: Planner,
    query: str,
    limit: int,
    trace_id: str,
    mode: str = "hybrid",
) -> QueryResult:
    """Arma el `PlanRequest`, delega en el Planner, traduce su resultado a
    `QueryResult` — la decisión "plan dinámico vs. fijo" vive en el Planner."""
    started = time.perf_counter()
    request = PlanRequest(query=query, trace_id=trace_id, mode=mode, limit=limit)

    try:
        plan, responses = await planner(request)
    except WritingSynthesisError as exc:
        raise SynthesisError(str(exc)) from exc

    writing_step = next((step for step in plan.steps if step.agent == "writing"), None)
    writing_response = responses.get(writing_step.id) if writing_step is not None else None
    elapsed_ms = (time.perf_counter() - started) * 1000

    if writing_response is None:
        # No debería pasar (el Planner garantiza exactamente un paso writing),
        # pero no se alucina una respuesta si de algún modo falta.
        return QueryResult(
            answer="No se pudo generar una respuesta.",
            evidence=[],
            confidence=0.0,
            plan=plan.steps,
            degraded=True,
            cost=Cost(ms=elapsed_ms),
        )

    return QueryResult(
        answer=str(writing_response.outputs.get("answer", "")),
        evidence=writing_response.evidence,
        confidence=writing_response.confidence,
        plan=plan.steps,
        degraded=plan.degraded,
        cost=Cost(ms=elapsed_ms),
    )
