"""Casos de uso del grafo de conocimiento: lectura, plantillas seguras de
consulta y corrección manual (doc 06 §2 Grafo, Sprint 9)."""

from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver

from kos_core.ontology import canonicalize
from kos_core.storage import neo4j as neo4j_storage

# Plantillas seguras de POST /v1/graph/query (doc 06 §2): nada de Cypher libre
# desde el body, solo estas funciones ya validadas.
QUERY_TEMPLATES = ("nodes_by_type", "neighbors_by_type", "most_connected")


async def get_node_with_neighborhood(
    driver: AsyncDriver, node_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    node = await neo4j_storage.get_node(driver, node_id)
    if node is None:
        return None
    neighbors = await neo4j_storage.get_neighborhood(driver, node_id)
    return node, neighbors


async def find_path(
    driver: AsyncDriver, from_id: str, to_id: str, *, max_hops: int = 4
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    return await neo4j_storage.find_path(driver, from_id, to_id, max_hops=max_hops)


async def nodes_by_type(
    driver: AsyncDriver, node_type: str, *, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    return await neo4j_storage.list_nodes_by_type(driver, node_type, cursor=cursor, limit=limit)


async def neighbors_by_type(
    driver: AsyncDriver, node_id: str, *, limit: int
) -> list[dict[str, Any]]:
    return await neo4j_storage.get_neighborhood(driver, node_id, limit=limit)


async def most_connected(
    driver: AsyncDriver, *, node_type: str | None, limit: int
) -> list[dict[str, Any]]:
    return await neo4j_storage.most_connected_nodes(driver, node_type=node_type, limit=limit)


async def correct_node(
    driver: AsyncDriver,
    node_id: str,
    *,
    canonical_name: str | None,
    node_type: str | None,
    aliases: list[str] | None,
) -> dict[str, Any] | None:
    """Corrección manual (doc 02 §4 regla 5): normaliza `canonical_name` con el
    mismo `canonicalize()` que usa entity resolution, para que el nodo corregido
    siga siendo deduplicable por futuros syncs."""
    normalized = canonicalize(canonical_name) if canonical_name is not None else None
    return await neo4j_storage.update_node(
        driver, node_id, canonical_name=normalized, node_type=node_type, aliases=aliases
    )


async def correct_relation(
    driver: AsyncDriver,
    relation_id: str,
    *,
    relation_type: str | None,
    confidence: float | None,
) -> dict[str, Any] | None:
    return await neo4j_storage.update_relation(
        driver, relation_id, relation_type=relation_type, confidence=confidence
    )


async def reject_relation(driver: AsyncDriver, relation_id: str) -> bool:
    return await neo4j_storage.reject_relation(driver, relation_id)
