"""Tasks de memoria (Sprint 12, doc 04): pipeline fijo de Celery, no agentes
reales todavía (doc 04 §1.1, Fase 4 no existe). `kos.memory_learn` destila una
consulta ya respondida en una memoria episódica; `kos.memory_consolidate`
(Celery beat, doc 04 §3 paso 2) agrupa episódicas repetidas en una semántica.
"""

from __future__ import annotations

import asyncio
import math
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_core.storage.postgres import create_engine
from kos_workers.celery_app import app

# Genera embeddings a partir de una lista de textos (Ollama real o fake en tests) —
# mismo patrón de inyección que `AsyncEmbed` en `graph_sync.py`.
AsyncEmbed = Callable[[list[str]], Awaitable[list[list[float]]]]

# Resuelve entities[] a partir de sources[] (doc 04 §2, decidido 2026-08-13): nodos
# del grafo que ya comparten alguna fuente con la memoria, sin extracción LLM nueva.
AsyncResolveEntities = Callable[[list[str]], Awaitable[list[str]]]

# Mismo criterio que entity resolution del grafo (Sprint 6, graph_sync.py):
# umbral fijo en código, no variable de entorno — parámetro de un algoritmo,
# no configuración de despliegue (doc 04 §6, revisión 2026-07-31).
DUPLICATE_THRESHOLD = 0.92
MIN_CLUSTER_SIZE = 3
INITIAL_SALIENCE = 0.5
CONSOLIDATED_BOOST = 0.2


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _learn_core(
    engine: AsyncEngine,
    *,
    query: str,
    answer: str,
    sources: list[str],
    confidence: float,
    embed: AsyncEmbed,
    resolve_entities: AsyncResolveEntities,
) -> dict[str, Any]:
    """Núcleo testeable con `embed`/`resolve_entities` fake (mismo estilo que
    `_sync_graph` en graph_sync.py: la task real inyecta Ollama/Neo4j, los tests
    inyectan stubs)."""
    content = f"Preguntó: {query!r} → {answer}"
    [embedding] = await embed([content])
    entities = await resolve_entities(sources)
    memory_id = uuid.uuid4()
    # doc 04 §5 (decidido 2026-08-13): no hay una confidence propia por fuente en
    # este dominio (a diferencia del grafo, `sources` acá no viene de una
    # extracción por documento) — todas arrancan del mismo `confidence` agregado
    # de la memoria; perder una fuente después sí las distingue vía la fórmula
    # de recálculo (`ALIAS_BOOST x n_restantes`, ver `retire_memory_sources`).
    source_refs = [{"doc_id": source, "confidence": confidence} for source in sources]
    await postgres_storage.insert_memory(
        engine,
        memory_id=memory_id,
        type="episodic",
        content=content,
        embedding=embedding,
        entities=entities,
        sources=source_refs,
        confidence=confidence,
        salience=INITIAL_SALIENCE,
    )
    return {"memory_id": str(memory_id)}


async def _async_memory_learn(
    *, query: str, answer: str, sources: list[str], confidence: float
) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    embedder = OllamaEmbeddingClient(settings)
    driver = neo4j_storage.create_driver(settings)

    async def resolve_entities(doc_ids: list[str]) -> list[str]:
        return await neo4j_storage.find_node_ids_by_sources(driver, doc_ids)

    try:
        return await _learn_core(
            engine,
            query=query,
            answer=answer,
            sources=sources,
            confidence=confidence,
            embed=embedder.embed,
            resolve_entities=resolve_entities,
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
