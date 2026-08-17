"""Tasks de memoria (Sprint 12, doc 04): `kos.memory_learn` destila una
consulta ya respondida en una memoria episódica; `kos.memory_consolidate`
(Celery beat, doc 04 §3 paso 2) agrupa episódicas repetidas en una semántica.

Sprint 21: `kos.memory_learn` deja de llamar `kos_core.memory_learn` directo
— construye un `LearningAgent` real (`packages/agents`) y lo invoca vía un
servidor MCP embebido en el worker (mismo patrón que `apps/api` usa desde
Sprint 17: `AppContext`/`create_server`/`EmbeddedToolCaller`, uno nuevo por
invocación de la task — igual que el engine/driver ya se creaban y cerraban
por task acá). Sigue siendo Celery, sigue sin bloquear `/v1/query` (doc 04:
"la UI nunca espera al aprendizaje") — el cambio es de orquestación interna,
no de comportamiento observable (doc 04 §1.1, la promesa de Fase 4)."""

from __future__ import annotations

import asyncio
import math
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_agents.learning import LearningAgent
from kos_agents.memory import MemoryAgent
from kos_core.config import Settings, get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.memory_learn import INITIAL_SALIENCE as INITIAL_SALIENCE
from kos_core.schemas.agents import AgentRequest
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_core.storage.postgres import create_engine
from kos_mcp.client import EmbeddedToolCaller
from kos_mcp.server import AppContext as MCPAppContext
from kos_mcp.server import create_server as create_mcp_server
from kos_workers.celery_app import app

# Mismo criterio que entity resolution del grafo (Sprint 6, graph_sync.py):
# umbral fijo en código, no variable de entorno — parámetro de un algoritmo,
# no configuración de despliegue (doc 04 §6, revisión 2026-07-31).
DUPLICATE_THRESHOLD = 0.92
MIN_CLUSTER_SIZE = 3
CONSOLIDATED_BOOST = 0.2


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _learn_via_agent_core(
    engine: AsyncEngine,
    driver: Any,
    embedder: OllamaEmbeddingClient,
    settings: Settings,
    *,
    query: str,
    answer: str,
    sources: list[str],
    confidence: float,
) -> dict[str, Any]:
    """Construye el `LearningAgent` real sobre un servidor MCP embebido
    (Sprint 21) y lo invoca — reemplaza la llamada directa a
    `kos_core.memory_learn.learn_from_query_answer` que este módulo tenía
    hasta Sprint 20."""
    mcp_context = MCPAppContext(
        settings=settings, postgres_engine=engine, neo4j_driver=driver, embedding_client=embedder
    )
    server = create_mcp_server(mcp_context)
    async with EmbeddedToolCaller(server) as caller:
        learning_agent = LearningAgent(MemoryAgent(caller))
        response = await learning_agent(
            AgentRequest(
                task="registrar interacción en memoria episódica (doc 04 §3 paso 1)",
                inputs={
                    "query": query,
                    "answer": answer,
                    "sources": sources,
                    "confidence": confidence,
                },
                trace_id=str(uuid.uuid4()),
            )
        )
    memory_id = response.outputs.get("memory_id")
    return {"memory_id": str(memory_id) if memory_id is not None else None}


async def _async_memory_learn(
    *, query: str, answer: str, sources: list[str], confidence: float
) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    embedder = OllamaEmbeddingClient(settings)
    driver = neo4j_storage.create_driver(settings)

    try:
        return await _learn_via_agent_core(
            engine,
            driver,
            embedder,
            settings,
            query=query,
            answer=answer,
            sources=sources,
            confidence=confidence,
        )
    finally:
        await embedder.aclose()
        await driver.close()
        await engine.dispose()


@app.task(name="kos.memory_learn")
def memory_learn(
    *, query: str, answer: str, sources: list[str], confidence: float
) -> dict[str, Any]:
    """Escritura de memoria episódica tras una consulta respondida (doc 04 §3
    paso 1); encolada desde `POST /v1/query` sin bloquear la respuesta al usuario."""
    return asyncio.run(
        _async_memory_learn(query=query, answer=answer, sources=sources, confidence=confidence)
    )


def _cluster_by_similarity(memories: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Agrupamiento greedy: cada memoria sin cluster arranca uno nuevo y se
    lleva a cualquier otra sin cluster con similitud > DUPLICATE_THRESHOLD.

    No es clustering general (no reconsidera fronteras ya trazadas) — alcanza
    para el volumen inicial de memoria (decenas, no miles) y es determinístico
    y testeable sin depender de un LLM para agrupar."""
    remaining = list(memories)
    clusters: list[list[dict[str, Any]]] = []
    while remaining:
        seed = remaining.pop(0)
        cluster = [seed]
        rest = []
        for candidate in remaining:
            if _cosine_similarity(seed["embedding"], candidate["embedding"]) > DUPLICATE_THRESHOLD:
                cluster.append(candidate)
            else:
                rest.append(candidate)
        remaining = rest
        clusters.append(cluster)
    return clusters


async def _consolidate_core(engine: AsyncEngine) -> dict[str, Any]:
    episodic = await postgres_storage.list_unconsolidated_episodic(engine)
    clusters = [c for c in _cluster_by_similarity(episodic) if len(c) >= MIN_CLUSTER_SIZE]
    for cluster in clusters:
        newest = max(cluster, key=lambda memory: memory["created_at"])
        content = f"Preguntaste {len(cluster)} veces por temas similares a: {newest['content']!r}"
        # Fusiona sources[] del cluster por doc_id, quedándose con la confidence
        # más alta vista para cada uno (doc 04 §5: incorporarla como si fuera
        # "nueva evidencia independiente", misma regla que la fila 1 de la tabla).
        merged_sources: dict[str, float] = {}
        for memory in cluster:
            for ref in memory["sources"]:
                merged_sources[ref["doc_id"]] = max(
                    merged_sources.get(ref["doc_id"], 0.0), ref["confidence"]
                )
        sources = [
            {"doc_id": doc_id, "confidence": conf}
            for doc_id, conf in sorted(merged_sources.items())
        ]
        avg_confidence = sum(memory["confidence"] for memory in cluster) / len(cluster)
        max_salience = max(memory["salience"] for memory in cluster)
        semantic_id = uuid.uuid4()
        await postgres_storage.insert_memory(
            engine,
            memory_id=semantic_id,
            type="semantic",
            content=content,
            embedding=newest["embedding"],
            entities=[],
            sources=sources,
            confidence=min(1.0, avg_confidence + CONSOLIDATED_BOOST),
            salience=min(1.0, max_salience + CONSOLIDATED_BOOST),
        )
        await postgres_storage.mark_superseded(
            engine, [memory["memory_id"] for memory in cluster], superseded_by=semantic_id
        )
    return {"episodic_seen": len(episodic), "semantic_created": len(clusters)}


async def _async_memory_consolidate() -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        return await _consolidate_core(engine)
    finally:
        await engine.dispose()


@app.task(name="kos.memory_consolidate")
def memory_consolidate() -> dict[str, Any]:
    """Job periódico (Celery beat, `KOS_MEMORY_CONSOLIDATION_HOURS`, doc 04 §3
    paso 2): agrupa episódicas repetidas (≥3, similitud > 0.92) en una semántica."""
    return asyncio.run(_async_memory_consolidate())
