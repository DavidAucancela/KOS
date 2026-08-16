"""Tests unitarios de `ResearchAgent` (Sprint 20): `ToolCaller` fake, sin MCP
ni infra real. Las tools que devuelven una lista llegan envueltas en
`{"result": [...]}` — así es como el SDK MCP serializa un retorno
`list[...]` top-level (verificado contra infra real, ver `research.py`)."""

from __future__ import annotations

from typing import Any

import pytest

from kos_agents.research import ResearchAgent
from kos_core.schemas.agents import AgentRequest, Constraints


class _FakeToolCaller:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return self.responses[name]


def _request(**inputs: Any) -> AgentRequest:
    return AgentRequest(
        task="research", inputs=inputs, constraints=Constraints(), trace_id="trace-1"
    )


async def test_github_repos_mapea_a_evidencia() -> None:
    caller = _FakeToolCaller(
        {
            "github.search_repos": {
                "result": [
                    {
                        "full_name": "tiangolo/fastapi",
                        "url": "https://github.com/tiangolo/fastapi",
                        "description": "FastAPI framework",
                        "stars": 70000,
                    }
                ]
            }
        }
    )
    agent = ResearchAgent(caller)

    response = await agent(_request(operation="github_repos", query="fastapi"))

    assert caller.calls == [("github.search_repos", {"query": "fastapi", "limit": 5})]
    assert len(response.evidence) == 1
    assert response.evidence[0].connector == "github"
    assert response.evidence[0].source_id == "https://github.com/tiangolo/fastapi"
    assert response.confidence == 1.0


async def test_github_commits_mapea_a_evidencia() -> None:
    # `message` ya viene truncada a la primera línea por `github.search_commits`
    # (kos_mcp.tools.github._search_commits_core) — el agente no re-trunca.
    caller = _FakeToolCaller(
        {
            "github.search_commits": {
                "result": [
                    {
                        "sha": "abcdef1234567890",
                        "url": "https://github.com/x/y/commit/abcdef1",
                        "message": "fix: bug crítico",
                        "repo": "x/y",
                    }
                ]
            }
        }
    )
    agent = ResearchAgent(caller)

    response = await agent(_request(operation="github_commits", query="bug"))

    assert response.evidence[0].quote == "fix: bug crítico"
    assert response.evidence[0].title == "x/y@abcdef1"


async def test_web_search_mapea_a_evidencia() -> None:
    caller = _FakeToolCaller(
        {
            "web.search": {
                "result": [
                    {
                        "title": "FastAPI docs",
                        "url": "https://fastapi.tiangolo.com",
                        "snippet": "...",
                    }
                ]
            }
        }
    )
    agent = ResearchAgent(caller)

    response = await agent(_request(operation="web_search", query="fastapi docs"))

    assert caller.calls == [("web.search", {"query": "fastapi docs", "limit": 5})]
    assert response.evidence[0].connector == "web"


async def test_web_open_devuelve_una_sola_evidencia_truncada() -> None:
    caller = _FakeToolCaller(
        {"web.open": {"url": "https://x.com", "title": "X", "text": "a" * 1000}}
    )
    agent = ResearchAgent(caller)

    response = await agent(_request(operation="web_open", url="https://x.com"))

    assert len(response.evidence) == 1
    assert len(response.evidence[0].quote) == 500


async def test_operacion_invalida_lanza_value_error() -> None:
    agent = ResearchAgent(_FakeToolCaller({}))

    with pytest.raises(ValueError, match="operation"):
        await agent(_request(operation="no-existe"))


async def test_sin_resultados_da_confidence_cero() -> None:
    caller = _FakeToolCaller({"web.search": {"result": []}})
    agent = ResearchAgent(caller)

    response = await agent(_request(operation="web_search", query="nada"))

    assert response.evidence == []
    assert response.confidence == 0.0
