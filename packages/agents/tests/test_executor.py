"""Tests unitarios de `execute_plan` (Sprint 18): agentes fake, sin infra real."""

from __future__ import annotations

from typing import Any

from kos_agents.planner.executor import execute_plan
from kos_core.schemas.agents import AgentRequest, AgentResponse
from kos_core.schemas.plan import PlanStep


class _FakeAgent:
    def __init__(self, name: str, calls: list[tuple[str, AgentRequest]]) -> None:
        self._name = name
        self._calls = calls

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        self._calls.append((self._name, request))
        return AgentResponse(
            outputs={"agent": self._name},
            evidence=[],
            confidence=0.5,
            trace_id=request.trace_id,
        )


async def test_pasos_sin_dependencias_corren_en_paralelo() -> None:
    calls: list[tuple[str, AgentRequest]] = []
    registry = {"retrieval": _FakeAgent("retrieval", calls), "graph": _FakeAgent("graph", calls)}
    steps = [
        PlanStep(id="s1", agent="retrieval", task="buscar", inputs={}),
        PlanStep(id="s2", agent="graph", task="grafo", inputs={"template": "most_connected"}),
    ]

    responses = await execute_plan(steps, registry, query="x", trace_id="trace-1")

    assert set(responses.keys()) == {"s1", "s2"}
    assert len(calls) == 2


async def test_writing_recibe_evidencia_fusionada_de_sus_dependencias() -> None:
    calls: list[tuple[str, AgentRequest]] = []

    class _EvidenceAgent:
        async def __call__(self, request: AgentRequest) -> AgentResponse:
            return AgentResponse(
                outputs={},
                evidence=[{"doc_id": None, "chunk_id": None, "quote": "algo"}],
                confidence=0.7,
                trace_id=request.trace_id,
            )

    class _WritingSpy:
        async def __call__(self, request: AgentRequest) -> AgentResponse:
            calls.append(("writing", request))
            return AgentResponse(
                outputs={"answer": "ok"}, evidence=[], confidence=0.0, trace_id=request.trace_id
            )

    registry: dict[str, Any] = {"retrieval": _EvidenceAgent(), "writing": _WritingSpy()}
    steps = [
        PlanStep(id="s1", agent="retrieval", task="buscar", inputs={}),
        PlanStep(id="s2", agent="writing", task="redactar", depends_on=["s1"]),
    ]

    await execute_plan(steps, registry, query="pregunta", trace_id="trace-1")

    [(_, writing_request)] = calls
    assert writing_request.inputs["query"] == "pregunta"
    assert len(writing_request.inputs["evidence"]) == 1
    assert writing_request.inputs["confidence"] == 0.7


async def test_graph_recibe_operation_query_forzado() -> None:
    calls: list[tuple[str, AgentRequest]] = []
    registry = {"graph": _FakeAgent("graph", calls)}
    steps = [PlanStep(id="s1", agent="graph", task="grafo", inputs={"template": "most_connected"})]

    await execute_plan(steps, registry, query="x", trace_id="trace-1")

    [(_, request)] = calls
    assert request.inputs["operation"] == "query"
    assert request.inputs["template"] == "most_connected"


async def test_paso_con_agente_desconocido_se_omite() -> None:
    steps = [PlanStep(id="s1", agent="research", task="no existe todavía", inputs={})]

    responses = await execute_plan(steps, {}, query="x", trace_id="trace-1")

    assert responses == {}


async def test_un_paso_de_evidencia_que_falla_degrada_en_vez_de_propagar() -> None:
    """Sprint 18, bug encontrado probando el Planner contra infra real: un
    input inválido generado por el LLM (ej. node_type='*') no debe tumbar
    toda la request con 500."""

    class _BrokenAgent:
        async def __call__(self, request: AgentRequest) -> AgentResponse:
            raise ValueError("Tipo de nodo desconocido: '*'")

    steps = [PlanStep(id="s1", agent="graph", task="grafo", inputs={"node_type": "*"})]

    responses = await execute_plan(steps, {"graph": _BrokenAgent()}, query="x", trace_id="trace-1")

    assert responses["s1"].evidence == []
    assert responses["s1"].outputs["degraded"] is True


async def test_fallo_del_paso_writing_se_propaga() -> None:
    """A diferencia de un paso de evidencia, `writing` sí debe propagar su
    fallo — no hay evidencia razonable con la que degradar la síntesis."""

    class _BrokenWriting:
        async def __call__(self, request: AgentRequest) -> AgentResponse:
            raise RuntimeError("ollama caído")

    steps = [PlanStep(id="s1", agent="writing", task="redactar", inputs={})]

    try:
        await execute_plan(steps, {"writing": _BrokenWriting()}, query="x", trace_id="trace-1")
        raise AssertionError("debía propagar el RuntimeError")
    except RuntimeError:
        pass
