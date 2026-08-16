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
