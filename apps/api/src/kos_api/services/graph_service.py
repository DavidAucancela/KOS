"""Casos de uso del grafo de conocimiento: lectura, plantillas seguras de
consulta y corrección manual (doc 06 §2 Grafo, Sprint 9)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from celery import Celery
from neo4j import AsyncDriver

from kos_core.config import Settings
from kos_core.ontology import canonicalize
from kos_core.storage import neo4j as neo4j_storage

# Plantillas seguras de POST /v1/graph/query (doc 06 §2): nada de Cypher libre
# desde el body, solo estas funciones ya validadas.
QUERY_TEMPLATES = ("nodes_by_type", "neighbors_by_type", "most_connected", "subgraph")

# La API no importa kos_workers: encola por nombre de task (doc 09 §2), mismo
# patrón que `source_service.enqueue_sync`.
RECOMMEND_TASK_NAME = "kos.recommend_from_graph_update"


@lru_cache(maxsize=4)
def _celery_client(redis_url: str) -> Celery:
    return Celery(broker=redis_url)


def enqueue_recommend(
    settings: Settings, *, node_ids: list[str], relation_ids: list[str], trace_id: str | None
) -> None:
    """Encadena el Recomendador (doc 11 §3) tras una corrección manual de
    grafo — mismo disparador que `kos.graph_sync` usa para el camino
    automático (Sprint 22)."""
    _celery_client(settings.redis_url).send_task(
        RECOMMEND_TASK_NAME,
        kwargs={"node_ids": node_ids, "relation_ids": relation_ids, "trace_id": trace_id},
        queue="default",
    )


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


async def subgraph(
    driver: AsyncDriver, *, node_type: str | None, limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Nodos más conectados + relaciones activas entre ellos (subgrafo inducido,
    doc 06 §2, Sprint 10): lo que necesita la visualización del grafo, sin traer
    vecinos fuera del conjunto mostrado."""
    nodes = await neo4j_storage.most_connected_nodes(driver, node_type=node_type, limit=limit)
    node_ids = [str(node["id"]) for node in nodes]
    relations = await neo4j_storage.subgraph_relations(driver, node_ids)
    return nodes, relations


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
