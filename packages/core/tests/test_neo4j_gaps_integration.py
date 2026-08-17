"""`gaps_by_prerequisite` contra Neo4j real (Sprint 23, doc 11 §4/§5).

Requiere: `make up` (Neo4j arriba). Corre solo con `-m integration` — mismo
motivo que `test_neo4j_integration.py`: los mocks no atrapan bugs de Cypher
reales.
"""

from __future__ import annotations

import uuid

import pytest

from kos_core.config import get_settings
from kos_core.storage import neo4j as neo4j_storage

pytestmark = pytest.mark.integration

_CONCEPT = "Concept"


async def _cleanup(driver: object, canonical_names: list[str]) -> None:
    async with driver.session() as session:  # type: ignore[attr-defined]
        await session.run(
            f"MATCH (n:{_CONCEPT}) WHERE n.canonical_name IN $names DETACH DELETE n",
            {"names": canonical_names},
        )


async def test_gaps_by_prerequisite_devuelve_prerequisito_debilmente_evidenciado() -> None:
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    suffix = uuid.uuid4().hex[:8]
    weak_canonical = f"test-gap-weak-{suffix}"
    strong_canonical = f"test-gap-strong-{suffix}"
    dependent_canonical = f"test-gap-dependent-{suffix}"
    try:
        weak_id = await neo4j_storage.merge_node(
            driver,
            node_type=_CONCEPT,
            canonical_name=weak_canonical,
            name="Weakly Evidenced Concept",
            aliases=[],
            confidence=0.3,
            sources=["doc-a"],
        )
        strong_id = await neo4j_storage.merge_node(
            driver,
            node_type=_CONCEPT,
            canonical_name=strong_canonical,
            name="Well Evidenced Concept",
            aliases=[],
            confidence=0.9,
            sources=["doc-a", "doc-b"],
        )
        dependent_id = await neo4j_storage.merge_node(
            driver,
            node_type=_CONCEPT,
            canonical_name=dependent_canonical,
            name="Dependent Concept",
            aliases=[],
            confidence=0.9,
            sources=["doc-a"],
        )
        await neo4j_storage.merge_relation(
            driver,
            source_id=weak_id,
            relation_type="PREREQUISITE_OF",
            target_id=dependent_id,
            confidence=0.9,
            sources=["doc-a"],
        )
        await neo4j_storage.merge_relation(
            driver,
            source_id=strong_id,
            relation_type="PREREQUISITE_OF",
            target_id=dependent_id,
            confidence=0.9,
            sources=["doc-a"],
        )

        candidates = await neo4j_storage.gaps_by_prerequisite(driver, limit=100)

        by_id = {c["node_id"]: c for c in candidates}
        assert weak_id in by_id
        assert strong_id not in by_id  # confidence 0.9 no cruza el umbral 0.5
        weak_candidate = by_id[weak_id]
        assert weak_candidate["confidence"] == pytest.approx(0.3)
        assert "Dependent Concept" in weak_candidate["blocks"]
    finally:
        await _cleanup(driver, [weak_canonical, strong_canonical, dependent_canonical])
        await driver.close()


async def test_gaps_by_prerequisite_respeta_el_umbral_de_confidence() -> None:
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    suffix = uuid.uuid4().hex[:8]
    prereq_canonical = f"test-gap-threshold-{suffix}"
    dependent_canonical = f"test-gap-threshold-dep-{suffix}"
    try:
        prereq_id = await neo4j_storage.merge_node(
            driver,
            node_type=_CONCEPT,
            canonical_name=prereq_canonical,
            name="Borderline Concept",
            aliases=[],
            confidence=0.6,
            sources=["doc-a"],
        )
        dependent_id = await neo4j_storage.merge_node(
            driver,
            node_type=_CONCEPT,
            canonical_name=dependent_canonical,
            name="Dependent Concept",
            aliases=[],
            confidence=0.9,
            sources=["doc-a"],
        )
        await neo4j_storage.merge_relation(
            driver,
            source_id=prereq_id,
            relation_type="PREREQUISITE_OF",
            target_id=dependent_id,
            confidence=0.9,
            sources=["doc-a"],
        )

        below_threshold = await neo4j_storage.gaps_by_prerequisite(
            driver, confidence_threshold=0.5, limit=100
        )
        above_threshold = await neo4j_storage.gaps_by_prerequisite(
            driver, confidence_threshold=0.7, limit=100
        )

        assert prereq_id not in {c["node_id"] for c in below_threshold}
        assert prereq_id in {c["node_id"] for c in above_threshold}
    finally:
        await _cleanup(driver, [prereq_canonical, dependent_canonical])
        await driver.close()
