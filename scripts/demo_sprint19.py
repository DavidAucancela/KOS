"""Demo del Sprint 19 (doc 08): "el plan se audita".

Tres escenarios: (1) un plan normal generado por `POST /v1/query` queda
persistido y se puede recuperar completo vía `GET /v1/plans/{id}` — mismos
`steps`/`degraded` en ambas respuestas; (2) un presupuesto de tiempo
(`timeout_s`) excedido corta la ejecución y deja el plan `degraded=True` con
`degraded_reason="budget_timeout"`, observable sin tumbar la respuesta; (3)
consultar un `plan_id` inexistente devuelve 404.

Requisitos: `make up`, `make migrate`, la API real corriendo (`make
dev-api`) para los escenarios (1) y (3). El escenario (2) corre standalone,
sin necesitar la API arriba.
Uso: `uv run python scripts/demo_sprint19.py`.
"""

import asyncio
import uuid

import httpx

from kos_agents.planner.planner import Planner
from kos_core.schemas.agents import AgentRequest, AgentResponse, Constraints
from kos_core.schemas.plan import PlanRequest

API_URL = "http://localhost:8000/v1/query"
PLANS_URL = "http://localhost:8000/v1/plans"


async def _demo_persistencia_via_api() -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(API_URL, json={"query": "¿qué es FastAPI?"})
        response.raise_for_status()
        body = response.json()
        plan_id = body["plan_id"]

        fetched = await client.get(f"{PLANS_URL}/{plan_id}")
        fetched.raise_for_status()
        fetched_body = fetched.json()

    plan_shape = [(s["id"], s["agent"]) for s in body["plan"]]
    fetched_shape = [(s["id"], s["agent"]) for s in fetched_body["steps"]]
    assert plan_shape == fetched_shape, "el plan persistido debe coincidir con el de /v1/query"
    assert fetched_body["degraded"] == body["degraded"]
    print(
        f"✓ Persistencia: plan_id={plan_id}, plan={plan_shape}, "
        f"elapsed_ms={fetched_body['elapsed_ms']:.1f}"
    )


async def _demo_404_via_api() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{PLANS_URL}/{uuid.uuid4()}")
    print(f"✓ 404 esperado para plan_id inexistente: status={response.status_code}")


class _SlowRetrieval:
    async def __call__(self, request: AgentRequest) -> AgentResponse:
        await asyncio.sleep(0.2)
        return AgentResponse(outputs={}, evidence=[], confidence=0.5, trace_id=request.trace_id)


class _NeverReached:
    async def __call__(self, request: AgentRequest) -> AgentResponse:
        raise AssertionError("no debía correr: el presupuesto ya se agotó")


class _FixedPlanLLM:
    """Devuelve siempre el mismo plan retrieval→writing en JSON."""

    async def generate(self, prompt: str, **kwargs: object) -> str:
        return (
            '[{"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, '
            '"depends_on": []}, {"id": "s2", "agent": "writing", "task": "redactar", '
            '"inputs": {}, "depends_on": ["s1"]}]'
        )


async def _demo_presupuesto_excedido_standalone() -> None:
    """Sin infra real: agentes fake, LLM fake — solo demuestra el enforcement
    de `timeout_s` y el `degraded_reason` observable."""
    planner = Planner(
        llm=_FixedPlanLLM(),
        retrieval_agent=_SlowRetrieval(),
        graph_agent=_NeverReached(),
        writing_agent=_NeverReached(),
    )
    plan, responses = await planner(
        PlanRequest(
            query="¿qué es KOS?",
            trace_id="demo-sprint19-timeout",
            constraints=Constraints(timeout_s=0.05),
        )
    )
    print(
        f"✓ Presupuesto de tiempo excedido: degraded={plan.degraded}, "
        f"degraded_reason={plan.degraded_reason!r}, "
        f"pasos completados={list(responses.keys())} de {[s.id for s in plan.steps]}"
    )


async def _demo_max_steps_standalone() -> None:
    """`max_steps` de 1 con un plan (fake) de 2 pasos degrada al plan fijo."""

    class _TwoStepLLM:
        async def generate(self, prompt: str, **kwargs: object) -> str:
            return (
                '[{"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, '
                '"depends_on": []}, {"id": "s2", "agent": "writing", "task": "redactar", '
                '"inputs": {}, "depends_on": ["s1"]}]'
            )

    class _NoopAgent:
        async def __call__(self, request: AgentRequest) -> AgentResponse:
            return AgentResponse(outputs={}, evidence=[], confidence=0.5, trace_id=request.trace_id)

    planner = Planner(
        llm=_TwoStepLLM(),
        retrieval_agent=_NoopAgent(),
        graph_agent=_NoopAgent(),
        writing_agent=_NoopAgent(),
    )
    plan, _responses = await planner(
        PlanRequest(
            query="x", trace_id="demo-sprint19-max-steps", constraints=Constraints(max_steps=1)
        )
    )
    print(
        f"✓ max_steps excedido: degraded={plan.degraded}, degraded_reason={plan.degraded_reason!r}"
    )


async def main() -> None:
    try:
        await _demo_persistencia_via_api()
        await _demo_404_via_api()
    except httpx.ConnectError:
        print("○ API no está corriendo en :8000 — saltando los escenarios contra la API")
    await _demo_presupuesto_excedido_standalone()
    await _demo_max_steps_standalone()


if __name__ == "__main__":
    asyncio.run(main())
