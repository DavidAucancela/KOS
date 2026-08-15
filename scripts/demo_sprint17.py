"""Demo del Sprint 17 (doc 08): "los agentes existen".

Dos partes: (1) `POST /v1/query` real, mostrando que la respuesta es idéntica
a la de antes del refactor pero ahora corre vía `RetrievalAgent` sobre MCP
(no `kos_core.storage` directo); (2) `GraphAgent`/`MemoryAgent` invocados
standalone contra infra real, en el mismo proceso, para probar que ya existen
y funcionan aunque `/v1/query` no los use todavía (esperan al Planner de
Sprint 18).

Requisitos: `make up`, `make pull-models`, `make migrate`, Ollama nativo con
el vault ya sincronizado, y la API real corriendo (`make dev-api` en otra
terminal) para la parte (1).
Uso: `uv run python scripts/demo_sprint17.py`.
"""

import asyncio
import uuid

import httpx

from kos_agents.graph import GraphAgent
from kos_agents.memory import MemoryAgent
from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.schemas.agents import AgentRequest, Constraints
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_mcp.client import EmbeddedToolCaller
from kos_mcp.server import AppContext, create_server

API_URL = "http://localhost:8000/v1/query"


async def _demo_query_via_api() -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(API_URL, json={"query": "¿qué es FastAPI?"})
    response.raise_for_status()
    body = response.json()
    plan_id = body["plan"][0]["id"]
    print(f"✓ POST /v1/query real: {len(body['evidence'])} evidencias, plan={plan_id}")
    print("  (retrieval corrió vía RetrievalAgent → MCP vector.search, no storage directo)")


async def _demo_agents_standalone() -> None:
    settings = get_settings()
    engine = postgres_storage.create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)
    app_context = AppContext(
        settings=settings, postgres_engine=engine, neo4j_driver=driver, embedding_client=embedder
    )
    server = create_server(app_context)
    marker = uuid.uuid4().hex[:8]
    try:
        async with EmbeddedToolCaller(server) as caller:
            graph_agent = GraphAgent(caller)
            graph_response = await graph_agent(
                AgentRequest(
                    task="nodos más conectados",
                    inputs={"operation": "query", "template": "most_connected", "limit": 3},
                    constraints=Constraints(),
                    trace_id="demo-sprint17-graph",
                )
            )
            print(
                f"✓ GraphAgent (standalone, sin conectar a /v1/query todavía): "
                f"{len(graph_response.evidence)} nodos"
            )

            memory_agent = MemoryAgent(caller)
            store_response = await memory_agent(
                AgentRequest(
                    task="guardar memoria de prueba",
                    inputs={
                        "operation": "store",
                        "query": f"[demo-sprint17-{marker}] pregunta de prueba",
                        "answer": "respuesta de prueba",
                        "sources": [],
                        "confidence": 0.5,
                        "confirm": True,
                    },
                    constraints=Constraints(),
                    trace_id="demo-sprint17-memory-store",
                )
            )
            print(f"✓ MemoryAgent.store → memory_id={store_response.outputs['memory_id']}")

            recall_response = await memory_agent(
                AgentRequest(
                    task="recuperar memoria de prueba",
                    inputs={"operation": "recall", "q": marker, "limit": 5},
                    constraints=Constraints(),
                    trace_id="demo-sprint17-memory-recall",
                )
            )
            print(f"✓ MemoryAgent.recall('{marker}') → {len(recall_response.evidence)} memoria(s)")
    finally:
        await engine.dispose()
        await driver.close()
        await embedder.aclose()


async def main() -> None:
    try:
        await _demo_query_via_api()
    except httpx.ConnectError:
        print("○ API no está corriendo en :8000 — saltando /v1/query (ver 'make dev-api')")
    await _demo_agents_standalone()


if __name__ == "__main__":
    asyncio.run(main())
