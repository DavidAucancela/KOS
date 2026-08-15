"""Núcleo de escritura de memoria episódica (doc 04 §3 paso 1), promovido a
`packages/core` en Sprint 16 para que dos vías de invocación compartan la misma
lógica ya testeada: `kos.memory_learn` (Celery, encolada sin bloquear desde
`POST /v1/query`, doc 04 §1.1) y la herramienta MCP `memory.store` (sincrónica,
in-process, devuelve el `memory_id` real de inmediato)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage import postgres as postgres_storage

AsyncEmbed = Callable[[list[str]], Awaitable[list[list[float]]]]

# Resuelve entities[] a partir de sources[] (doc 04 §2, decidido 2026-08-13): nodos
# del grafo que ya comparten alguna fuente con la memoria, sin extracción LLM nueva.
AsyncResolveEntities = Callable[[list[str]], Awaitable[list[str]]]

INITIAL_SALIENCE = 0.5


async def learn_from_query_answer(
    engine: AsyncEngine,
    *,
    query: str,
    answer: str,
    sources: list[str],
    confidence: float,
    embed: AsyncEmbed,
    resolve_entities: AsyncResolveEntities,
) -> uuid.UUID:
    """Destila una consulta ya respondida en una memoria episódica (doc 04 §3).

    `embed`/`resolve_entities` inyectados (Ollama/Neo4j reales o stubs en
    tests, mismo patrón que `_sync_graph` en `graph_sync.py`).
    """
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
    return memory_id
