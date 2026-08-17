"""ResearchAgent (doc 03 §2/§3): busca fuera del vault vía las herramientas MCP
externas `github.search_repos`, `github.search_commits`, `web.search`,
`web.open` (doc 06 §4, Sprint 20). Mismo patrón que `GraphAgent`: un
`operation` en `inputs` decide qué tool MCP invocar.

Todas de lectura — sin gate de `permissions.py` (no está en `WRITE_TOOLS`).

Las tres operaciones que devuelven una lista (`github_repos`/`github_commits`/
`web_search`) llegan envueltas en `{"result": [...]}` — a diferencia de
`GraphAgent`, cuyas tools siempre devuelven un objeto con listas anidadas
(`NodeWithNeighborhood`, `GraphQueryResponse`...), estas tools MCP devuelven
`list[...]` en el top-level, y el SDK MCP envuelve cualquier tipo de retorno
que no sea un objeto en `{"result": ...}` para el `structured_content` del
protocolo (encontrado probando standalone contra la API real de GitHub —
ningún test con fakes lo hubiera atrapado, mismo patrón que se repite en este
proyecto: doc `docs/deuda-tecnica.md`)."""

from __future__ import annotations

import time
from typing import Any

from kos_agents.base import ToolCaller
from kos_core.schemas.agents import AgentRequest, AgentResponse, Cost, EvidenceRef

_OPERATIONS = ("github_repos", "github_commits", "web_search", "web_open")


def _unwrap_list(result: dict[str, Any]) -> list[dict[str, Any]]:
    return list(result["result"])


class ResearchAgent:
    def __init__(self, tool_caller: ToolCaller) -> None:
        self._tool_caller = tool_caller

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        operation = request.inputs.get("operation")
        if operation not in _OPERATIONS:
            raise ValueError(
                f"ResearchAgent.inputs['operation'] debe ser uno de {_OPERATIONS}, no {operation!r}"
            )

        evidence: list[EvidenceRef]
        if operation == "github_repos":
            result = await self._tool_caller.call_tool(
                "github.search_repos",
                {"query": request.inputs["query"], "limit": request.inputs.get("limit", 5)},
            )
            evidence = [
                EvidenceRef(
                    source_id=item["url"],
                    connector="github",
                    title=item["full_name"],
                    quote=item.get("description") or item["full_name"],
                    score=None,
                )
                for item in _unwrap_list(result)
            ]
        elif operation == "github_commits":
            result = await self._tool_caller.call_tool(
                "github.search_commits",
                {"query": request.inputs["query"], "limit": request.inputs.get("limit", 5)},
            )
            evidence = [
                EvidenceRef(
                    source_id=item["url"],
                    connector="github",
                    title=f"{item['repo']}@{item['sha'][:7]}",
                    quote=item["message"],
                    score=None,
                )
                for item in _unwrap_list(result)
            ]
        elif operation == "web_search":
            result = await self._tool_caller.call_tool(
                "web.search",
                {"query": request.inputs["query"], "limit": request.inputs.get("limit", 5)},
            )
            evidence = [
                EvidenceRef(
                    source_id=item["url"],
                    connector="web",
                    title=item["title"],
                    quote=item["snippet"],
                    score=None,
                )
                for item in _unwrap_list(result)
            ]
        else:
            result = await self._tool_caller.call_tool("web.open", {"url": request.inputs["url"]})
            evidence = [
                EvidenceRef(
                    source_id=result["url"],
                    connector="web",
                    title=result.get("title"),
                    quote=str(result["text"])[:500],
                    score=None,
                )
            ]

        elapsed_ms = (time.perf_counter() - started) * 1000
        return AgentResponse(
            outputs={"result_count": len(evidence)},
            evidence=evidence,
            confidence=1.0 if evidence else 0.0,
            cost=Cost(ms=elapsed_ms),
            trace_id=request.trace_id,
        )
