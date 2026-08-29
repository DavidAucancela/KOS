"""Tests unitarios de `Planner` (Sprint 18): LLM/agentes fake, sin infra real."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from kos_agents.planner.planner import Planner, parse_plan_response
from kos_core.schemas.agents import AgentRequest, AgentResponse, Constraints
from kos_core.schemas.plan import PlanRequest


class _FakeAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[AgentRequest] = []

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        self.calls.append(request)
        return AgentResponse(
            outputs={"agent": self.name},
            evidence=[{"doc_id": None, "chunk_id": None, "quote": f"evidencia de {self.name}"}],
            confidence=0.6,
            trace_id=request.trace_id,
        )


class _ScriptedLLM:
    """Devuelve, en orden, cada elemento de `responses`; lanza si se agotan."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.calls += 1
        return self._responses.pop(0)


def test_parse_plan_response_tolera_fences_de_markdown() -> None:
    raw = (
        "```json\n"
        '[{"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, "depends_on": []},\n'
        ' {"id": "s2", "agent": "writing", "task": "redactar", "inputs": {}, '
        '"depends_on": ["s1"]}]\n'
        "```"
    )
    steps = parse_plan_response(raw, query="x")
    assert steps is not None
    assert [s.id for s in steps] == ["s1", "s2"]


def test_parse_plan_response_json_invalido_devuelve_none() -> None:
    assert parse_plan_response("no es json", query="x") is None


def test_parse_plan_response_descarta_confirm_de_los_inputs() -> None:
    """CLAUDE.md regla 7 / deuda `memory.store`: el LLM no elige `confirm` — se
    quita del paso para que el plan persistido no muestre un `confirm: true`
    engañoso."""
    raw = json.dumps(
        [
            {
                "id": "s1",
                "agent": "memory",
                "task": "store",
                "inputs": {"operation": "store", "confirm": True},
                "depends_on": [],
            },
            {
                "id": "s2",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1"],
            },
        ]
    )
    steps = parse_plan_response(raw, query="x")
    assert steps is not None
    assert "confirm" not in steps[0].inputs
    assert steps[0].inputs["operation"] == "store"


def test_parse_plan_response_requiere_exactamente_un_writing_con_dependencia() -> None:
    sin_writing = json.dumps(
        [{"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, "depends_on": []}]
    )
    assert parse_plan_response(sin_writing, query="x") is None

    writing_sin_depender = json.dumps(
        [{"id": "s1", "agent": "writing", "task": "redactar", "inputs": {}, "depends_on": []}]
    )
    assert parse_plan_response(writing_sin_depender, query="x") is None


def test_parse_plan_response_rechaza_dependencia_a_id_inexistente() -> None:
    raw = json.dumps(
        [
            {
                "id": "s1",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["no-existe"],
            }
        ]
    )
    assert parse_plan_response(raw, query="x") is None


async def test_planner_usa_el_plan_dinamico_si_valida() -> None:
    plan_json = json.dumps(
        [
            {"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, "depends_on": []},
            {
                "id": "s2",
                "agent": "graph",
                "task": "grafo",
                "inputs": {"template": "most_connected"},
                "depends_on": [],
            },
            {
                "id": "s3",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1", "s2"],
            },
        ]
    )
    llm = _ScriptedLLM([plan_json])
    retrieval, graph, writing = _FakeAgent("retrieval"), _FakeAgent("graph"), _FakeAgent("writing")
    planner = Planner(llm=llm, retrieval_agent=retrieval, graph_agent=graph, writing_agent=writing)

    plan, responses = await planner(
        PlanRequest(query="¿qué relaciona FastAPI?", trace_id="trace-1")
    )

    assert plan.degraded is False
    assert plan.degraded_reason is None
    assert [s.id for s in plan.steps] == ["s1", "s2", "s3"]
    assert set(responses.keys()) == {"s1", "s2", "s3"}
    assert llm.calls == 1


async def test_planner_arma_post_con_paso_learning_tras_responder() -> None:
    plan_json = json.dumps(
        [
            {"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, "depends_on": []},
            {
                "id": "s2",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1"],
            },
        ]
    )
    llm = _ScriptedLLM([plan_json])
    retrieval, graph, writing = _FakeAgent("retrieval"), _FakeAgent("graph"), _FakeAgent("writing")
    planner = Planner(llm=llm, retrieval_agent=retrieval, graph_agent=graph, writing_agent=writing)

    plan, _responses = await planner(PlanRequest(query="¿qué es FastAPI?", trace_id="trace-1"))

    assert [s.id for s in plan.post] == ["post-learning"]
    post_step = plan.post[0]
    assert post_step.agent == "learning"
    assert post_step.depends_on == ["s2"]
    assert post_step.inputs["query"] == "¿qué es FastAPI?"
    assert post_step.confidence is None  # declarativo: execute_plan no lo corre


async def test_planner_ejecuta_un_paso_memory_si_esta_registrado() -> None:
    plan_json = json.dumps(
        [
            {
                "id": "s1",
                "agent": "memory",
                "task": "recordar conversaciones previas",
                "inputs": {"operation": "recall", "q": "fastapi"},
                "depends_on": [],
            },
            {
                "id": "s2",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1"],
            },
        ]
    )
    llm = _ScriptedLLM([plan_json])
    retrieval, graph, writing = _FakeAgent("retrieval"), _FakeAgent("graph"), _FakeAgent("writing")
    memory = _FakeAgent("memory")
    planner = Planner(
        llm=llm,
        retrieval_agent=retrieval,
        graph_agent=graph,
        writing_agent=writing,
        memory_agent=memory,
    )

    plan, responses = await planner(
        PlanRequest(query="¿de qué hablamos sobre fastapi?", trace_id="t")
    )

    assert plan.degraded is False
    assert set(responses.keys()) == {"s1", "s2"}
    assert len(memory.calls) == 1


async def test_planner_ejecuta_un_paso_research_si_esta_registrado() -> None:
    plan_json = json.dumps(
        [
            {
                "id": "s1",
                "agent": "research",
                "task": "buscar en github",
                "inputs": {"operation": "github_repos", "query": "fastapi"},
                "depends_on": [],
            },
            {
                "id": "s2",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1"],
            },
        ]
    )
    llm = _ScriptedLLM([plan_json])
    retrieval, graph, writing = _FakeAgent("retrieval"), _FakeAgent("graph"), _FakeAgent("writing")
    research = _FakeAgent("research")
    planner = Planner(
        llm=llm,
        retrieval_agent=retrieval,
        graph_agent=graph,
        writing_agent=writing,
        research_agent=research,
    )

    plan, responses = await planner(PlanRequest(query="¿qué es fastapi en GitHub?", trace_id="t"))

    assert plan.degraded is False
    assert set(responses.keys()) == {"s1", "s2"}
    assert len(research.calls) == 1


async def test_planner_sin_research_agent_no_registra_ese_paso() -> None:
    """Compatibilidad: `research_agent` es opcional — un plan que igual lo
    pida simplemente no encuentra el agente, y `s1` nunca resuelve
    (`executor.py` trata un `agent` fuera del registry igual que una
    dependencia que nunca resuelve: `s2` tampoco corre porque depende de `s1`)."""
    plan_json = json.dumps(
        [
            {
                "id": "s1",
                "agent": "research",
                "task": "buscar en github",
                "inputs": {"operation": "github_repos", "query": "fastapi"},
                "depends_on": [],
            },
            {
                "id": "s2",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1"],
            },
        ]
    )
    llm = _ScriptedLLM([plan_json])
    retrieval, graph, writing = _FakeAgent("retrieval"), _FakeAgent("graph"), _FakeAgent("writing")
    planner = Planner(llm=llm, retrieval_agent=retrieval, graph_agent=graph, writing_agent=writing)

    plan, responses = await planner(PlanRequest(query="¿qué es fastapi en GitHub?", trace_id="t"))

    assert "s1" not in responses
    assert "s2" not in responses
    assert plan.degraded is True


async def test_planner_degrada_al_plan_fijo_tras_dos_fallos() -> None:
    llm = _ScriptedLLM(["no es json", "tampoco esto"])
    retrieval, graph, writing = _FakeAgent("retrieval"), _FakeAgent("graph"), _FakeAgent("writing")
    planner = Planner(llm=llm, retrieval_agent=retrieval, graph_agent=graph, writing_agent=writing)

    plan, responses = await planner(PlanRequest(query="¿qué es KOS?", trace_id="trace-2"))

    assert plan.degraded is True
    assert plan.degraded_reason == "llm_generation"
    assert [s.agent for s in plan.steps] == ["retrieval", "writing"]
    assert set(responses.keys()) == {"s1", "s2"}
    assert llm.calls == 2


async def test_planner_reintenta_una_vez_con_el_error_antes_de_degradar() -> None:
    plan_json = json.dumps(
        [
            {"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, "depends_on": []},
            {
                "id": "s2",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1"],
            },
        ]
    )
    llm = _ScriptedLLM(["no válido", plan_json])
    retrieval, graph, writing = _FakeAgent("retrieval"), _FakeAgent("graph"), _FakeAgent("writing")
    planner = Planner(llm=llm, retrieval_agent=retrieval, graph_agent=graph, writing_agent=writing)

    plan, _responses = await planner(PlanRequest(query="x", trace_id="trace-3"))

    assert plan.degraded is False
    assert llm.calls == 2


async def test_max_steps_excedido_degrada_al_plan_fijo() -> None:
    """Sprint 19: un plan dinámico con más pasos de los permitidos por
    `constraints.max_steps` no se ejecuta tal cual — cae al plan fijo, misma
    red de seguridad que un fallo de generación."""
    plan_json = json.dumps(
        [
            {"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, "depends_on": []},
            {
                "id": "s2",
                "agent": "graph",
                "task": "grafo",
                "inputs": {"template": "most_connected"},
                "depends_on": [],
            },
            {
                "id": "s3",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1", "s2"],
            },
        ]
    )
    llm = _ScriptedLLM([plan_json])
    retrieval, graph, writing = _FakeAgent("retrieval"), _FakeAgent("graph"), _FakeAgent("writing")
    planner = Planner(llm=llm, retrieval_agent=retrieval, graph_agent=graph, writing_agent=writing)

    plan, responses = await planner(
        PlanRequest(query="x", trace_id="trace-4", constraints=Constraints(max_steps=2))
    )

    assert plan.degraded is True
    assert plan.degraded_reason == "budget_max_steps"
    assert [s.agent for s in plan.steps] == ["retrieval", "writing"]
    assert set(responses.keys()) == {"s1", "s2"}


async def test_timeout_s_del_plan_degrada_con_motivo_observable() -> None:
    """Sprint 19: un plan que se corta por presupuesto de tiempo queda
    marcado `degraded=True` con `degraded_reason="budget_timeout"`, distinto
    de una degradación por fallo de generación o de un paso individual."""

    class _SlowRetrieval:
        async def __call__(self, request: AgentRequest) -> AgentResponse:
            await asyncio.sleep(0.05)
            return AgentResponse(outputs={}, evidence=[], confidence=0.5, trace_id=request.trace_id)

    plan_json = json.dumps(
        [
            {"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, "depends_on": []},
            {
                "id": "s2",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1"],
            },
        ]
    )
    llm = _ScriptedLLM([plan_json])
    planner = Planner(
        llm=llm,
        retrieval_agent=_SlowRetrieval(),
        graph_agent=_FakeAgent("graph"),
        writing_agent=_FakeAgent("writing"),
    )

    plan, responses = await planner(
        PlanRequest(query="x", trace_id="trace-5", constraints=Constraints(timeout_s=0.01))
    )

    assert plan.degraded is True
    assert plan.degraded_reason == "budget_timeout"
    assert set(responses.keys()) == {"s1"}
