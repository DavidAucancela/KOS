"""Cliente de Neo4j (ADR-0003: fuente de verdad de las relaciones).

Escritura de nodos/relaciones (Sprint 6, doc 05 §3-4): las etiquetas de nodo y los
tipos de relación de Cypher no aceptan parámetros — por eso `node_type`/
`relation_type` se validan contra la ontología cerrada (`kos_core.ontology`) antes
de interpolarlos en la query. Los valores agregados (alias fusionados, sources
acumulados, confianza recalculada) los computa quien llama (`kos.graph_sync`,
la entity resolution vive ahí, no aquí) — estas funciones solo persisten.
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from kos_core.config import Settings
from kos_core.ontology import is_valid_node_type, is_valid_relation_type


def create_driver(settings: Settings) -> AsyncDriver:
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )


async def ping(driver: AsyncDriver) -> None:
    await driver.verify_connectivity()


class NodeRecord(dict[str, Any]):
    """Fila de nodo tal cual la devuelve Neo4j (id, canonical_name, name, aliases,
    confidence, sources)."""


async def fetch_nodes_by_type(driver: AsyncDriver, node_type: str) -> list[NodeRecord]:
    """Candidatos existentes de un tipo, para entity resolution (doc 05 §4 paso 3)."""
    if not is_valid_node_type(node_type):
        raise ValueError(f"Tipo de nodo desconocido: {node_type!r}")
    query = (
        f"MATCH (n:{node_type}) RETURN n.id AS id, n.canonical_name AS canonical_name, "
        "n.name AS name, n.aliases AS aliases, n.confidence AS confidence, "
        "n.sources AS sources"
    )
    async with driver.session() as session:
        result = await session.run(query)
        return [NodeRecord(record) async for record in result]


async def merge_node(
    driver: AsyncDriver,
    *,
    node_type: str,
    canonical_name: str,
    name: str,
    aliases: list[str],
    confidence: float,
    sources: list[str],
) -> str:
    """Crea o actualiza el nodo por `canonical_name` (clave de dedupe, doc 02 §4).

    Los valores (`aliases`/`sources`/`confidence`) ya vienen fusionados por quien
    llama — entity resolution decide qué fusionar, esto solo persiste el resultado.
    """
    if not is_valid_node_type(node_type):
        raise ValueError(f"Tipo de nodo desconocido: {node_type!r}")
    query = (
        f"MERGE (n:{node_type} {{canonical_name: $canonical_name}}) "
        "ON CREATE SET n.id = $id, n.created_at = datetime(), n.version = 1 "
        "ON MATCH SET n.version = n.version + 1 "
        "SET n.name = $name, n.aliases = $aliases, n.confidence = $confidence, "
        "n.sources = $sources, n.updated_at = datetime() "
        "RETURN n.id AS id"
    )
    params = {
        "canonical_name": canonical_name,
        "id": str(uuid.uuid4()),
        "name": name,
        "aliases": aliases,
        "confidence": confidence,
        "sources": sources,
    }
    async with driver.session() as session:
        result = await session.run(query, params)
        record = await result.single()
        assert record is not None  # MERGE siempre devuelve una fila
        return str(record["id"])


async def merge_relation(
    driver: AsyncDriver,
    *,
    source_id: str,
    relation_type: str,
    target_id: str,
    confidence: float,
    sources: list[str],
    extracted_by: str = "parser@v1",
) -> None:
    """Crea o actualiza la relación entre dos nodos ya resueltos (por `id`)."""
    if not is_valid_relation_type(relation_type):
        raise ValueError(f"Tipo de relación desconocido: {relation_type!r}")
    query = (
        "MATCH (a {id: $source_id}), (b {id: $target_id}) "
        f"MERGE (a)-[r:{relation_type}]->(b) "
        "ON CREATE SET r.extracted_by = $extracted_by, r.extracted_at = datetime() "
        "SET r.confidence = $confidence, r.sources = $sources"
    )
    params = {
        "source_id": source_id,
        "target_id": target_id,
        "confidence": confidence,
        "sources": sources,
        "extracted_by": extracted_by,
    }
    async with driver.session() as session:
        await session.run(query, params)
