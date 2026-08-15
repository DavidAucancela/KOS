"""Tests de integración de los agentes (Sprint 17) contra infra real: mismo
`EmbeddedToolCaller` que usará `apps/api`, conectado al servidor MCP embebido
(`kos_mcp.server.create_server`). Requiere `make up` y Ollama nativo. Corre
solo con `-m integration`.

`packages/agents` no depende de `packages/mcp-tools` (doc 09 §2) — este test
sí puede importar ambos, porque vive fuera de `kos_agents` y solo verifica que
la combinación funciona de punta a punta, el mismo rol que cumple `apps/api`
en producción."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from kos_agents.graph import GraphAgent
from kos_agents.memory import MemoryAgent
from kos_agents.retrieval import RetrievalAgent
from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.schemas.agents import AgentRequest, Constraints
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_core.storage.postgres import memory_items_table
from kos_mcp.client import EmbeddedToolCaller
from kos_mcp.server import AppContext, create_server

pytestmark = pytest.mark.integration

_NODE_TYPE = "Technology"


async def _cleanup_nodes(driver: object, canonical_names: list[str]) -> None:
    async with driver.session() as session:  # type: ignore[attr-defined]
        await session.run(
            f"MATCH (n:{_NODE_TYPE}) WHERE n.canonical_name IN $names DETACH DELETE n",
            {"names": canonical_names},
        )


async def test_retrieval_graph_memory_agents_contra_infra_real() -> None:
    settings = get_settings()
    engine = postgres_storage.create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)
    app_context = AppContext(
        settings=settings, postgres_engine=engine, neo4j_driver=driver, embedding_client=embedder
    )
    server = create_server(app_context)
    canonical = f"test-agents-{uuid.uuid4().hex[:8]}"
    memory_ids: list[uuid.UUID] = []
    try:
        node_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical,
            name=canonical,
            aliases=[],
            confidence=0.8,
            sources=["doc-a"],
        )

        async with EmbeddedToolCaller(server) as caller:
            retrieval = RetrievalAgent(caller)
            retrieval_response = await retrieval(
                AgentRequest(
                    task="buscar evidencia",
                    inputs={"query": "FastAPI", "limit": 3},
                    constraints=Constraints(),
                    trace_id="test-trace-retrieval",
                )
            )
            assert retrieval_response.trace_id == "test-trace-retrieval"

            graph_agent = GraphAgent(caller)
            graph_response = await graph_agent(
                AgentRequest(
                    task="obtener nodo",
                    inputs={"operation": "get_node", "node_id": node_id},
                    constraints=Constraints(),
                    trace_id="test-trace-graph",
                )
            )
            assert len(graph_response.evidence) == 1
            assert graph_response.evidence[0].node_id is not None

            memory_agent = MemoryAgent(caller)
            store_response = await memory_agent(
                AgentRequest(
                    task="guardar memoria",
                    inputs={
                        "operation": "store",
                        "query": f"[{canonical}] pregunta de prueba",
                        "answer": "respuesta de prueba",
                        "sources": [],
                        "confidence": 0.5,
                        "confirm": True,
                    },
                    constraints=Constraints(),
                    trace_id="test-trace-memory",
                )
            )
            assert store_response.outputs["approved"] is True
            memory_ids.append(uuid.UUID(str(store_response.outputs["memory_id"])))

            recall_response = await memory_agent(
                AgentRequest(
                    task="recuperar memoria",
                    inputs={"operation": "recall", "q": canonical, "limit": 5},
                    constraints=Constraints(),
                    trace_id="test-trace-recall",
                )
            )
            assert len(recall_response.evidence) == 1
    finally:
        if memory_ids:
            async with engine.begin() as conn:  # type: ignore[attr-defined]
                await conn.execute(
                    delete(memory_items_table).where(memory_items_table.c.memory_id.in_(memory_ids))
                )
        await _cleanup_nodes(driver, [canonical])
        await engine.dispose()
        await driver.close()
        await embedder.aclose()
