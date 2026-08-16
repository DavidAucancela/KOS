"""Demo del Sprint 20 (doc 08): "el mundo entra".

Cuatro escenarios: (1) `ResearchAgent.github_repos` contra la API real de
GitHub (sin `GITHUB_TOKEN`, cuota liviana pero funcional); (2)
`ResearchAgent.web_open` trayendo una página real; (3) `ResearchAgent.web_search`
sin `BRAVE_SEARCH_API_KEY` configurada: llamado standalone (no vía Planner) el
error sube como `ToolError` claro, no en silencio — es `executor.py` (Sprint
18) quien sabe degradar un paso de evidencia que falla, no el agente; (4) una
pregunta real a `/v1/query` que pide contexto externo genera un plan con un
paso `research` (el LLM decide, no una heurística) — solo si el modelo local
elige research (no está garantizado con un LLM chico, doc 03 §3).

Requisitos: `make up`, Ollama nativo, la API real corriendo (`make dev-api`)
para el escenario (4). Los escenarios (1)-(3) corren standalone.
Uso: `uv run python scripts/demo_sprint20.py`.
"""

import asyncio

import httpx

from kos_agents.research import ResearchAgent
from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.schemas.agents import AgentRequest, Constraints
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_mcp.client import EmbeddedToolCaller, ToolError
from kos_mcp.server import AppContext, create_server

API_URL = "http://localhost:8000/v1/query"


async def _demo_research_agent_standalone() -> None:
    settings = get_settings()
    engine = postgres_storage.create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)
    app_context = AppContext(
        settings=settings, postgres_engine=engine, neo4j_driver=driver, embedding_client=embedder
    )
    server = create_server(app_context)
    try:
        async with EmbeddedToolCaller(server) as caller:
            research_agent = ResearchAgent(caller)

            repos_response = await research_agent(
                AgentRequest(
                    task="repos de fastapi en GitHub",
                    inputs={"operation": "github_repos", "query": "fastapi", "limit": 3},
                    constraints=Constraints(),
                    trace_id="demo-sprint20-github",
                )
            )
            print(f"✓ github_repos (API real, sin token): {len(repos_response.evidence)} repos")
            for ev in repos_response.evidence:
                print(f"    - {ev.title}: {ev.source_id}")

            open_response = await research_agent(
                AgentRequest(
                    task="leer la doc de FastAPI",
                    inputs={"operation": "web_open", "url": "https://fastapi.tiangolo.com"},
                    constraints=Constraints(),
                    trace_id="demo-sprint20-webopen",
                )
            )
            chars = len(open_response.evidence[0].quote or "") if open_response.evidence else 0
            print(f"✓ web_open (fetch real): {chars} caracteres de texto extraído")

            search_request = AgentRequest(
                task="buscar en la web",
                inputs={"operation": "web_search", "query": "fastapi"},
                constraints=Constraints(),
                trace_id="demo-sprint20-websearch",
            )
            if settings.brave_search_api_key:
                search_response = await research_agent(search_request)
                print(f"✓ web_search: {len(search_response.evidence)} resultados (con API key)")
            else:
                try:
                    await research_agent(search_request)
                except ToolError as exc:
                    print(f"✓ web_search sin BRAVE_SEARCH_API_KEY: falla con error claro ({exc})")
                    print(
                        "  (vía Planner, executor.py degradaría este paso en vez de "
                        "romper la respuesta — Sprint 18)"
                    )
    finally:
        await engine.dispose()
        await driver.close()
        await embedder.aclose()


async def _demo_via_api() -> None:
    query = "¿cuál es el repositorio de GitHub más popular sobre FastAPI y qué dice su README?"
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(API_URL, json={"query": query})
    response.raise_for_status()
    body = response.json()
    plan_shape = [(step["id"], step["agent"]) for step in body["plan"]]
    used_research = any(agent == "research" for _id, agent in plan_shape)
    print(f"✓ POST /v1/query real: plan={plan_shape}, degraded={body['degraded']}")
    print(f"  research usado en el plan: {used_research}")


async def main() -> None:
    await _demo_research_agent_standalone()
    try:
        await _demo_via_api()
    except httpx.ConnectError:
        print("○ API no está corriendo en :8000 — saltando el escenario vía Planner real")


if __name__ == "__main__":
    asyncio.run(main())
