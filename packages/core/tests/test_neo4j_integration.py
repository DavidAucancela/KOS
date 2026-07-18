"""Escritura real a Neo4j (Sprint 6, doc 05 §3-4).

Requiere: `make up` (Neo4j arriba). Corre solo con `-m integration`. No depende
del LLM real — la extracción vía LLM ya está cubierta con fakes en
`apps/workers/tests/test_graph_sync_task.py`; esto verifica el camino de
escritura real (MERGE idempotente + relaciones), que es la parte nueva de
infraestructura de este sprint.
"""

from __future__ import annotations

import uuid

import pytest

from kos_core.config import get_settings
from kos_core.storage import neo4j as neo4j_storage

pytestmark = pytest.mark.integration

# Tipo real de la ontología, canonical_name único por corrida para no chocar
# con datos reales si el test corre contra una base con contenido.
_NODE_TYPE = "Technology"


async def _cleanup(driver: object, canonical_names: list[str]) -> None:
    async with driver.session() as session:  # type: ignore[attr-defined]
        await session.run(
            f"MATCH (n:{_NODE_TYPE}) WHERE n.canonical_name IN $names DETACH DELETE n",
            {"names": canonical_names},
        )


async def test_merge_node_es_idempotente() -> None:
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonical = f"test-entity-{uuid.uuid4().hex[:8]}"
    try:
        first_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical,
            name="Test Entity",
            aliases=["te"],
            confidence=0.5,
            sources=["doc-a"],
        )
        second_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical,
            name="Test Entity",
            aliases=["te", "test-e"],
            confidence=0.8,
            sources=["doc-a", "doc-b"],
        )
        assert first_id == second_id  # mismo canonical_name → mismo nodo, no duplicado

        candidates = await neo4j_storage.fetch_nodes_by_type(driver, _NODE_TYPE)
        matching = [c for c in candidates if c["canonical_name"] == canonical]
        assert len(matching) == 1
        assert matching[0]["confidence"] == 0.8
        assert set(matching[0]["sources"]) == {"doc-a", "doc-b"}
    finally:
        await _cleanup(driver, [canonical])
        await driver.close()


async def test_merge_relation_conecta_dos_nodos() -> None:
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonical_a = f"test-source-{uuid.uuid4().hex[:8]}"
    canonical_b = f"test-target-{uuid.uuid4().hex[:8]}"
    try:
        source_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical_a,
            name="Source",
            aliases=[],
            confidence=0.9,
            sources=["doc-a"],
        )
        target_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical_b,
            name="Target",
            aliases=[],
            confidence=0.9,
            sources=["doc-a"],
        )
        await neo4j_storage.merge_relation(
            driver,
            source_id=source_id,
            relation_type="USES",
            target_id=target_id,
            confidence=0.9,
            sources=["doc-a"],
        )

        async with driver.session() as session:
            result = await session.run(
                "MATCH (a {id: $source_id})-[r:USES]->(b {id: $target_id}) "
                "RETURN r.confidence AS confidence",
                {"source_id": source_id, "target_id": target_id},
            )
            record = await result.single()
        assert record is not None
        assert record["confidence"] == 0.9
    finally:
        await _cleanup(driver, [canonical_a, canonical_b])
        await driver.close()
