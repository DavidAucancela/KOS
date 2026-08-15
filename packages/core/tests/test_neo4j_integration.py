"""Escritura y lectura real en Neo4j (Sprint 6 y 9, doc 05 §3-4, doc 06 §2).

Requiere: `make up` (Neo4j arriba). Corre solo con `-m integration`. No depende
del LLM real — la extracción vía LLM ya está cubierta con fakes en
`apps/workers/tests/test_graph_sync_task.py`; esto verifica el camino de
escritura/lectura real (MERGE idempotente, relaciones, vecindario, caminos y
la protección de correcciones manuales contra `merge_node`/`merge_relation`).
Sprint 8 dejó la lección de que los mocks no atrapan bugs de tipos SQL/Cypher
reales — por eso estas queries nuevas se prueban acá, no solo con mocks.
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


async def test_get_node_y_get_neighborhood() -> None:
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

        node = await neo4j_storage.get_node(driver, source_id)
        assert node is not None
        assert node["canonical_name"] == canonical_a
        assert node["node_type"] == _NODE_TYPE
        assert node["locked"] is False

        assert await neo4j_storage.get_node(driver, "no-existe") is None

        neighbors = await neo4j_storage.get_neighborhood(driver, source_id)
        assert len(neighbors) == 1
        assert neighbors[0]["direction"] == "outgoing"
        assert neighbors[0]["neighbor_id"] == target_id
        assert neighbors[0]["relation_type"] == "USES"

        neighbors_target = await neo4j_storage.get_neighborhood(driver, target_id)
        assert len(neighbors_target) == 1
        assert neighbors_target[0]["direction"] == "incoming"
    finally:
        await _cleanup(driver, [canonical_a, canonical_b])
        await driver.close()


async def test_find_path_entre_dos_nodos() -> None:
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonical_a = f"test-a-{uuid.uuid4().hex[:8]}"
    canonical_b = f"test-b-{uuid.uuid4().hex[:8]}"
    canonical_c = f"test-c-{uuid.uuid4().hex[:8]}"
    try:
        id_a = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical_a,
            name="A",
            aliases=[],
            confidence=0.9,
            sources=["doc-a"],
        )
        id_b = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical_b,
            name="B",
            aliases=[],
            confidence=0.9,
            sources=["doc-a"],
        )
        id_c = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical_c,
            name="C",
            aliases=[],
            confidence=0.9,
            sources=["doc-a"],
        )
        await neo4j_storage.merge_relation(
            driver,
            source_id=id_a,
            relation_type="RELATED_TO",
            target_id=id_b,
            confidence=0.9,
            sources=["doc-a"],
        )
        await neo4j_storage.merge_relation(
            driver,
            source_id=id_b,
            relation_type="RELATED_TO",
            target_id=id_c,
            confidence=0.9,
            sources=["doc-a"],
        )

        found = await neo4j_storage.find_path(driver, id_a, id_c)
        assert found is not None
        nodes, relations = found
        assert [n["id"] for n in nodes] == [id_a, id_b, id_c]
        assert len(relations) == 2

        assert await neo4j_storage.find_path(driver, id_a, "no-existe") is None
    finally:
        await _cleanup(driver, [canonical_a, canonical_b, canonical_c])
        await driver.close()


async def test_update_node_bloquea_confidence_ante_un_merge_posterior() -> None:
    """doc 02 §4 regla 5: el usuario siempre gana."""
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonical = f"test-locked-{uuid.uuid4().hex[:8]}"
    try:
        node_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical,
            name="Docker",
            aliases=[],
            confidence=0.4,
            sources=["doc-a"],
        )
        corrected = await neo4j_storage.update_node(
            driver, node_id, canonical_name="docker-corrected"
        )
        assert corrected is not None
        assert corrected["locked"] is True
        assert corrected["extracted_by"] == "user"
        assert corrected["confidence"] == 1.0
        assert corrected["canonical_name"] == "docker-corrected"

        # Un re-sync posterior (mismo canonical_name que el nodo ya tiene) no
        # debería pisar name/aliases/confidence, aunque sí sumar la nueva fuente.
        await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name="docker-corrected",
            name="Docker (mal extraído de nuevo)",
            aliases=["docker-alt"],
            confidence=0.3,
            sources=["doc-a", "doc-b"],
        )
        after_sync = await neo4j_storage.get_node(driver, node_id)
        assert after_sync is not None
        assert after_sync["name"] == "Docker"
        assert after_sync["aliases"] == []
        assert after_sync["confidence"] == 1.0
        assert set(after_sync["sources"]) == {"doc-a", "doc-b"}

        assert await neo4j_storage.update_node(driver, "no-existe") is None
    finally:
        await _cleanup(driver, [canonical, "docker-corrected"])
        await driver.close()


async def test_update_relation_y_reject_relation() -> None:
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
            confidence=0.5,
            sources=["doc-a"],
        )
        neighbors = await neo4j_storage.get_neighborhood(driver, source_id)
        relation_id = neighbors[0]["rel_id"]

        corrected = await neo4j_storage.update_relation(
            driver, relation_id, relation_type="RELATED_TO"
        )
        assert corrected is not None
        assert corrected["relation_type"] == "RELATED_TO"
        assert corrected["extracted_by"] == "user"
        assert corrected["confidence"] == 1.0
        assert corrected["id"] == relation_id  # el id se preserva pese al DELETE+CREATE

        rejected = await neo4j_storage.reject_relation(driver, relation_id)
        assert rejected is True
        assert await neo4j_storage.get_neighborhood(driver, source_id) == []

        # Un re-sync (mismo tipo original, USES) no debería resucitar la relación.
        await neo4j_storage.merge_relation(
            driver,
            source_id=source_id,
            relation_type="RELATED_TO",
            target_id=target_id,
            confidence=0.9,
            sources=["doc-b"],
        )
        assert await neo4j_storage.get_neighborhood(driver, source_id) == []

        assert await neo4j_storage.reject_relation(driver, "no-existe") is False
    finally:
        await _cleanup(driver, [canonical_a, canonical_b])
        await driver.close()


async def test_update_node_bloquea_duplicado_si_sync_propone_el_tipo_viejo() -> None:
    """Bug real encontrado en Sprint 9 probando contra el vault real (no lo
    atrapaban los mocks): tras un `PATCH` que cambia el tipo (label real vía
    APOC), el nodo corregido dejaba de coincidir con el patrón
    `MERGE (n:{node_type} ...)` si el pipeline volvía a proponer el tipo viejo,
    y `merge_node` creaba un duplicado bajo la label vieja en vez de respetar
    la corrección."""
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonical = f"test-crosstype-{uuid.uuid4().hex[:8]}"
    try:
        node_id = await neo4j_storage.merge_node(
            driver,
            node_type="Organization",
            canonical_name=canonical,
            name="Docker Desktop",
            aliases=[],
            confidence=0.6,
            sources=["doc-a"],
        )
        corrected = await neo4j_storage.update_node(driver, node_id, node_type="Technology")
        assert corrected is not None
        assert corrected["node_type"] == "Technology"

        # El pipeline vuelve a proponer "Organization" (el tipo viejo, mal
        # clasificado) para el mismo canonical_name.
        returned_id = await neo4j_storage.merge_node(
            driver,
            node_type="Organization",
            canonical_name=canonical,
            name="Docker Desktop (re-extraído)",
            aliases=["docker desktop"],
            confidence=0.5,
            sources=["doc-b"],
        )
        assert returned_id == node_id  # no crea un nodo Organization duplicado

        async with driver.session() as session:
            result = await session.run(
                "MATCH (n) WHERE n.canonical_name = $canonical "
                "RETURN n.id AS id, labels(n)[0] AS node_type, n.sources AS sources",
                {"canonical": canonical},
            )
            rows = [dict(r) async for r in result]
        assert len(rows) == 1
        assert rows[0]["node_type"] == "Technology"
        assert set(rows[0]["sources"]) == {"doc-a", "doc-b"}
    finally:
        async with driver.session() as session:
            await session.run(
                "MATCH (n) WHERE n.canonical_name = $canonical DETACH DELETE n",
                {"canonical": canonical},
            )
        await driver.close()


async def test_list_nodes_by_type_paginado_y_most_connected() -> None:
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonicals = [f"test-page-{i}-{uuid.uuid4().hex[:8]}" for i in range(3)]
    try:
        ids = []
        for canonical in canonicals:
            ids.append(
                await neo4j_storage.merge_node(
                    driver,
                    node_type=_NODE_TYPE,
                    canonical_name=canonical,
                    name=canonical,
                    aliases=[],
                    confidence=0.9,
                    sources=["doc-a"],
                )
            )
        await neo4j_storage.merge_relation(
            driver,
            source_id=ids[0],
            relation_type="RELATED_TO",
            target_id=ids[1],
            confidence=0.9,
            sources=["doc-a"],
        )
        await neo4j_storage.merge_relation(
            driver,
            source_id=ids[0],
            relation_type="RELATED_TO",
            target_id=ids[2],
            confidence=0.9,
            sources=["doc-a"],
        )

        assert await neo4j_storage.count_relations(driver, ids[0]) == 2

        page, next_cursor = await neo4j_storage.list_nodes_by_type(driver, _NODE_TYPE, limit=1000)
        found = {row["canonical_name"] for row in page} & set(canonicals)
        assert found == set(canonicals)
        assert next_cursor is None

        most_connected = await neo4j_storage.most_connected_nodes(
            driver, node_type=_NODE_TYPE, limit=1000
        )
        top = next(row for row in most_connected if row["id"] == ids[0])
        assert top["canonical_name"] == canonicals[0]

        # Subgrafo inducido (Sprint 10): solo la relación entre ids[0] e ids[1]
        # está "dentro" del conjunto — la de ids[0]->ids[2] queda afuera si
        # ids[2] no se incluye, aunque ids[2] exista en el grafo.
        induced = await neo4j_storage.subgraph_relations(driver, [ids[0], ids[1]])
        assert {r["source_id"] for r in induced} == {ids[0]}
        assert {r["target_id"] for r in induced} == {ids[1]}

        full = await neo4j_storage.subgraph_relations(driver, ids)
        assert len(full) == 2

        assert await neo4j_storage.subgraph_relations(driver, []) == []
    finally:
        await _cleanup(driver, canonicals)
        await driver.close()


async def test_find_node_ids_by_sources_devuelve_nodos_que_comparten_fuente() -> None:
    """Sprint 13 (doc 04 §2): entity-linking de memoria reusa esta lookup en vez
    de extraer entidades del contenido destilado con un LLM."""
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    matching_canonical = f"test-linked-{uuid.uuid4().hex[:8]}"
    other_canonical = f"test-unlinked-{uuid.uuid4().hex[:8]}"
    canonicals = [matching_canonical, other_canonical]
    try:
        matching_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=matching_canonical,
            name=matching_canonical,
            aliases=[],
            confidence=0.8,
            sources=["doc-shared"],
        )
        await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=other_canonical,
            name=other_canonical,
            aliases=[],
            confidence=0.8,
            sources=["doc-other"],
        )

        found = await neo4j_storage.find_node_ids_by_sources(driver, ["doc-shared", "doc-x"])
        assert found == [matching_id]

        assert await neo4j_storage.find_node_ids_by_sources(driver, []) == []
        assert await neo4j_storage.find_node_ids_by_sources(driver, ["doc-no-existe"]) == []
    finally:
        await _cleanup(driver, canonicals)
        await driver.close()


async def test_retire_document_recalcula_confidence_con_las_fuentes_que_sobreviven() -> None:
    """Sprint 14 (doc 04 §5, decidido 2026-08-13): confidence_nueva =
    min(1.0, max(confidence_base restantes) + ALIAS_BOOST x (n_restantes - 1))."""
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonical = f"test-recalc-{uuid.uuid4().hex[:8]}"
    try:
        node_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical,
            name=canonical,
            aliases=[],
            confidence=0.9,
            sources=["doc-a", "doc-b", "doc-c"],
            source_confidences=[0.6, 0.9, 0.7],
        )

        result = await neo4j_storage.retire_document(driver, "doc-b")
        assert result == {"relations_deleted": 0, "nodes_deleted": 0}

        node = await neo4j_storage.get_node(driver, node_id)
        assert node is not None
        assert set(node["sources"]) == {"doc-a", "doc-c"}
        # max(0.6, 0.7) + ALIAS_BOOST(0.05) * (2 restantes - 1) = 0.75
        assert node["confidence"] == pytest.approx(0.75)

        # Retirar otra fuente: solo queda doc-c (confidence base 0.7), sin boost.
        await neo4j_storage.retire_document(driver, "doc-a")
        node = await neo4j_storage.get_node(driver, node_id)
        assert node is not None
        assert node["sources"] == ["doc-c"]
        assert node["confidence"] == pytest.approx(0.7)
    finally:
        await _cleanup(driver, [canonical])
        await driver.close()


async def test_retire_document_borra_huerfanos_y_protege_lo_locked() -> None:
    """Sprint 11 (doc 05 §5, doc 06 §3 `document.deleted`): al tumbar un
    documento, lo que se queda sin ninguna fuente se borra — salvo lo `locked`,
    que sobrevive porque el usuario ya lo validó."""
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    orphan_canonical = f"test-retire-orphan-{uuid.uuid4().hex[:8]}"
    survivor_canonical = f"test-retire-survivor-{uuid.uuid4().hex[:8]}"
    locked_canonical = f"test-retire-locked-{uuid.uuid4().hex[:8]}"
    canonicals = [orphan_canonical, survivor_canonical, locked_canonical]
    try:
        orphan_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=orphan_canonical,
            name=orphan_canonical,
            aliases=[],
            confidence=0.8,
            sources=["doc-x"],
        )
        survivor_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=survivor_canonical,
            name=survivor_canonical,
            aliases=[],
            confidence=0.8,
            sources=["doc-x", "doc-y"],
        )
        locked_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=locked_canonical,
            name=locked_canonical,
            aliases=[],
            confidence=0.8,
            sources=["doc-x"],
        )
        await neo4j_storage.update_node(driver, locked_id, canonical_name=locked_canonical)
        assert (await neo4j_storage.get_node(driver, locked_id))["locked"] is True

        # Relación solo respaldada por doc-x entre orphan y survivor: debe
        # desaparecer aunque uno de sus extremos (survivor) sobreviva.
        await neo4j_storage.merge_relation(
            driver,
            source_id=orphan_id,
            relation_type="RELATED_TO",
            target_id=survivor_id,
            confidence=0.8,
            sources=["doc-x"],
        )

        result = await neo4j_storage.retire_document(driver, "doc-x")
        assert result == {"relations_deleted": 1, "nodes_deleted": 1}

        assert await neo4j_storage.get_node(driver, orphan_id) is None
        survivor = await neo4j_storage.get_node(driver, survivor_id)
        assert survivor is not None
        assert survivor["sources"] == ["doc-y"]
        assert survivor["id"] == survivor_id  # sigue existiendo

        locked = await neo4j_storage.get_node(driver, locked_id)
        assert locked is not None
        assert locked["sources"] == []  # sin fuentes, pero protegido por locked
        assert locked["confidence"] == 1.0  # doc 04 §5: corrección del usuario, inmutable

        neighborhood = await neo4j_storage.get_neighborhood(driver, survivor_id)
        assert neighborhood == []  # la relación huérfana no sobrevive
    finally:
        await _cleanup(driver, canonicals)
        await driver.close()
