"""Tests unitarios de `WritingAgent` (Sprint 18): LLM fake, sin infra real."""

from __future__ import annotations

from typing import Any

import pytest

from kos_agents.writing import NO_EVIDENCE_ANSWER, SynthesisError, WritingAgent
from kos_core.schemas.agents import AgentRequest, Constraints


def _request(**inputs: Any) -> AgentRequest:
    return AgentRequest(
        task="redactar respuesta", inputs=inputs, constraints=Constraints(), trace_id="trace-1"
    )


class _EchoLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.calls += 1
        return "Respuesta con citas [1]."

    async def aclose(self) -> None:
        return None


class _FailingLLM:
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("ollama caído")

    async def aclose(self) -> None:
        return None


async def test_sin_evidencia_no_llama_al_llm() -> None:
    llm = _EchoLLM()
    agent = WritingAgent(llm)

    response = await agent(_request(query="¿qué es KOS?", evidence=[], confidence=0.0))

    assert llm.calls == 0
    assert response.outputs["answer"] == NO_EVIDENCE_ANSWER
    assert response.confidence == 0.0


async def test_con_evidencia_llama_al_llm_y_propaga_confidence() -> None:
    llm = _EchoLLM()
    agent = WritingAgent(llm)
    evidence = [{"doc_id": None, "chunk_id": None, "quote": "FastAPI es un framework"}]

    response = await agent(_request(query="¿qué es FastAPI?", evidence=evidence, confidence=0.8))

    assert llm.calls == 1
    assert response.outputs["answer"] == "Respuesta con citas [1]."
    assert response.confidence == 0.8
    assert len(response.evidence) == 1


async def test_fallo_del_llm_lanza_synthesis_error() -> None:
    agent = WritingAgent(_FailingLLM())
    evidence = [{"doc_id": None, "chunk_id": None, "quote": "algo"}]

    with pytest.raises(SynthesisError):
        await agent(_request(query="x", evidence=evidence, confidence=0.5))


class _FakeToolCaller:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return self.response


async def test_sintesis_nunca_llama_tools_aunque_haya_tool_caller() -> None:
    caller = _FakeToolCaller({})
    agent = WritingAgent(_EchoLLM(), tool_caller=caller)
    evidence = [{"doc_id": None, "chunk_id": None, "quote": "algo"}]

    await agent(_request(query="x", evidence=evidence, confidence=0.5))

    assert caller.calls == []


async def test_update_note_fuerza_confirm_true() -> None:
    caller = _FakeToolCaller({"approved": True, "path": "Ideas/Nota.md"})
    agent = WritingAgent(_EchoLLM(), tool_caller=caller)

    ok = await agent.update_note("Ideas/Nota.md", "cuerpo nuevo", trace_id="t")

    assert ok is True
    assert caller.calls == [
        (
            "obsidian.update_note",
            {
                "path": "Ideas/Nota.md",
                "content": "cuerpo nuevo",
                "source_name": None,
                "confirm": True,
                "trace_id": "t",
            },
        )
    ]


async def test_read_note_fuerza_confirm_true_y_devuelve_contenido() -> None:
    caller = _FakeToolCaller({"approved": True, "path": "Nota.md", "content": "cuerpo"})
    agent = WritingAgent(_EchoLLM(), tool_caller=caller)

    content = await agent.read_note("Nota.md", trace_id="t")

    assert content == "cuerpo"
    assert caller.calls[0][0] == "obsidian.read_note"
    assert caller.calls[0][1]["confirm"] is True


async def test_create_folder_fuerza_confirm_true() -> None:
    caller = _FakeToolCaller({"approved": True, "path": "Ideas/Sub"})
    agent = WritingAgent(_EchoLLM(), tool_caller=caller)

    ok = await agent.create_folder("Ideas/Sub", trace_id="t")

    assert ok is True
    assert caller.calls[0][0] == "obsidian.create_folder"
    assert caller.calls[0][1]["confirm"] is True


async def test_operar_sobre_vault_sin_tool_caller_falla() -> None:
    agent = WritingAgent(_EchoLLM())

    with pytest.raises(RuntimeError):
        await agent.create_folder("Ideas/Sub", trace_id="t")
