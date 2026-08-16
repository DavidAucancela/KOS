"""Ejecutor de planes (doc 03 §3 regla 1): agrupa pasos por dependencias
resueltas y corre cada grupo en paralelo (`asyncio.gather`) — un paso corre en
cuanto todos los pasos de los que depende ya tienen respuesta, sin esperar a
los que le son independientes.

El paso `writing` no arma su propia evidencia: el executor le inyecta la
evidencia fusionada (concatenada) y la confidence (máxima) de los pasos de los
que depende — ni el LLM ni el plan fijo tienen que construir eso a mano. El
paso `graph` (Sprint 18: catálogo acotado a `graph.query`, ver `planner.py`)
recibe `operation="query"` forzado, sin que el LLM tenga que saberlo.
"""

from __future__ import annotations

import asyncio
from typing import Any

from kos_agents.base import Agent
from kos_core.schemas.agents import AgentRequest, AgentResponse, Constraints
from kos_core.schemas.plan import PlanStep


def _step_inputs(
    step: PlanStep, responses: dict[str, AgentResponse], *, query: str
) -> dict[str, Any]:
    if step.agent == "retrieval":
        return {**step.inputs, "query": query}
    if step.agent == "graph":
        return {**step.inputs, "operation": "query"}
    if step.agent == "writing":
        evidence: list[Any] = []
        confidences: list[float] = []
        for dep_id in step.depends_on:
            dep_response = responses.get(dep_id)
            if dep_response is None:
                continue
            evidence.extend(dep_response.evidence)
            confidences.append(dep_response.confidence)
        return {
            "query": query,
            "evidence": evidence,
            "confidence": max(confidences) if confidences else 0.0,
        }
    return dict(step.inputs)


async def execute_plan(
    steps: list[PlanStep],
    registry: dict[str, Agent],
    *,
    query: str,
    trace_id: str,
) -> dict[str, AgentResponse]:
    """Corre `steps` respetando `depends_on`, en oleadas paralelas. Un paso
    cuyo `agent` no está en `registry`, o cuya dependencia nunca resuelve
    (ciclo/id inexistente — ya debería haberse descartado en la validación del
    Planner), simplemente no aparece en el resultado."""
    responses: dict[str, AgentResponse] = {}
    remaining = list(steps)

    while remaining:
        ready = [step for step in remaining if set(step.depends_on) <= responses.keys()]
        if not ready:
            break
        remaining = [step for step in remaining if step not in ready]

        async def run_step(step: PlanStep) -> tuple[str, AgentResponse] | None:
            agent = registry.get(step.agent)
            if agent is None:
                return None
            inputs = _step_inputs(step, responses, query=query)
            request = AgentRequest(
                task=step.task, inputs=inputs, constraints=Constraints(), trace_id=trace_id
            )
            if step.agent == "writing":
                # La síntesis SÍ debe propagar su fallo (mapeado a 503 por
                # `apps/api` vía `SynthesisError`) — acá no hay evidencia
                # razonable con la que degradar.
                response = await agent(request)
                return step.id, response
            try:
                response = await agent(request)
            except Exception:
                # Un paso de evidencia que falla (ej. el LLM propuso un input
                # inválido para una tool) no debe tumbar todo el plan con un
                # 500 — mismo espíritu que la degradación a búsqueda léxica
                # cuando falla el embedder (doc 06: mejor algo que nada).
                response = AgentResponse(
                    outputs={"degraded": True}, evidence=[], confidence=0.0, trace_id=trace_id
                )
            return step.id, response

        results = await asyncio.gather(*(run_step(step) for step in ready))
        for result in results:
            if result is not None:
                step_id, response = result
                responses[step_id] = response

    return responses
