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

from kos_core.confidence import ALIAS_BOOST
from kos_core.config import Settings
from kos_core.ontology import is_valid_node_type, is_valid_relation_type


def create_driver(settings: Settings) -> AsyncDriver:
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )


async def ping(driver: AsyncDriver) -> None:
    await driver.verify_connectivity()


def _normalize_temporals(value: Any) -> Any:
    """El driver de Neo4j expone sus propios tipos temporales (`neo4j.time.DateTime`),
    no `datetime.datetime` nativo — Pydantic (schemas/graph.py) rechaza el primero.
    Recursivo porque `find_path` devuelve listas de mapas con fechas anidadas."""
    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        return to_native()
    if isinstance(value, dict):
        return {key: _normalize_temporals(v) for key, v in value.items()}
    if isinstance(value, list):
        return [_normalize_temporals(v) for v in value]
    return value


class NodeRecord(dict[str, Any]):
    """Fila de nodo tal cual la devuelve Neo4j (id, canonical_name, name, aliases,
    confidence, sources)."""

    def __init__(self, record: Any) -> None:
        super().__init__(_normalize_temporals(dict(record)))


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


async def fetch_nodes_by_ids(driver: AsyncDriver, node_ids: list[str]) -> list[NodeRecord]:
    """Batch por `id` (doc 12 §4): arma la bolsa de entidades de dos documentos
    distintos para el prompt de relaciones cross-documento sin una consulta
    por id. `node_ids` puede traer duplicados (mismo nodo referenciado desde
    varios chunks) — Neo4j los devuelve una sola vez, `IN` no repite filas."""
    if not node_ids:
        return []
    query = (
        "MATCH (n) WHERE n.id IN $node_ids "
        "RETURN n.id AS id, n.canonical_name AS canonical_name, "
        "n.name AS name, n.aliases AS aliases, n.confidence AS confidence, "
        "n.sources AS sources"
    )
    async with driver.session() as session:
        result = await session.run(query, {"node_ids": node_ids})
        return [NodeRecord(record) async for record in result]


async def fetch_node_by_canonical_name(
    driver: AsyncDriver, node_type: str, canonical_name: str
) -> NodeRecord | None:
    """Match exacto por `canonical_name` + tipo (doc 05 §4 paso 2, doc 12 §3): trae
    un solo nodo en vez de todos los del tipo, a diferencia de `fetch_nodes_by_type`
    — el camino barato de entity resolution no necesita más que esto."""
    if not is_valid_node_type(node_type):
        raise ValueError(f"Tipo de nodo desconocido: {node_type!r}")
    query = (
        f"MATCH (n:{node_type} {{canonical_name: $canonical_name}}) "
        "RETURN n.id AS id, n.canonical_name AS canonical_name, "
        "n.name AS name, n.aliases AS aliases, n.confidence AS confidence, "
        "n.sources AS sources, n.source_confidences AS source_confidences"
    )
    async with driver.session() as session:
        result = await session.run(query, {"canonical_name": canonical_name})
        record = await result.single()
        return NodeRecord(record) if record is not None else None


async def merge_node(
    driver: AsyncDriver,
    *,
    node_type: str,
    canonical_name: str,
    name: str,
    aliases: list[str],
    confidence: float,
    sources: list[str],
    source_confidences: list[float] | None = None,
) -> str:
    """Crea o actualiza el nodo por `canonical_name` (clave de dedupe, doc 02 §4).

    Los valores (`aliases`/`sources`/`confidence`) ya vienen fusionados por quien
    llama — entity resolution decide qué fusionar, esto solo persiste el resultado.
    `source_confidences` (doc 04 §5, decidido 2026-08-13) es un array paralelo a
    `sources` (mismo índice): la confidence "cruda" con la que se agregó cada
    fuente, para poder recalcular al perder una (Neo4j no admite listas de
    objetos como propiedad). Si se omite, no se toca — el nodo queda sin esa
    traza hasta la próxima fusión que sí la pase.

    Si el nodo está `locked` (corrección manual, Sprint 9, doc 02 §4 regla 5), el
    sync sigue sumando `sources` como evidencia pero no pisa `name`/`aliases`/
    `confidence` — la protección vive acá, no en quien llama, para que aplique
    sin importar qué compute el caller. Tampoco se actualiza `source_confidences`
    en ese caso: la confianza de un nodo corregido es inmutable para el pipeline
    (doc 04 §5 tabla, "Corrección del usuario"), así que no hace falta trazar por
    fuente algo que nunca se va a recalcular.

    Un `PATCH` que corrige el tipo cambia la label real (`update_node`, vía APOC):
    el nodo corregido deja de coincidir con el patrón `MERGE (n:{node_type} ...)`
    de acá si el pipeline vuelve a proponer el tipo viejo — sin este chequeo previo
    por `canonical_name` sin importar la label, esa desincronización crearía un
    duplicado en vez de respetar la corrección (bug real encontrado en Sprint 9
    probando contra el vault real, no por los tests mockeados). Solo aplica a
    nodos `locked`: el resto conserva el comportamiento de Sprint 6 (nodos con el
    mismo `canonical_name` pero tipos distintos pueden coexistir — polisemia).
    """
    if not is_valid_node_type(node_type):
        raise ValueError(f"Tipo de nodo desconocido: {node_type!r}")
    async with driver.session() as session:
        locked_result = await session.run(
            "MATCH (n {canonical_name: $canonical_name}) WHERE coalesce(n.locked, false) "
            "SET n.sources = apoc.coll.toSet(coalesce(n.sources, []) + $sources), "
            "n.updated_at = datetime() "
            "RETURN n.id AS id",
            {"canonical_name": canonical_name, "sources": sources},
        )
        locked_record = await locked_result.single()
        if locked_record is not None:
            return str(locked_record["id"])

        query = (
            f"MERGE (n:{node_type} {{canonical_name: $canonical_name}}) "
            "ON CREATE SET n.id = $id, n.created_at = datetime(), n.version = 1, "
            "n.locked = false, n.extracted_by = 'parser@v1' "
            "ON MATCH SET n.version = n.version + 1 "
            "SET n.name = $name, n.aliases = $aliases, n.confidence = $confidence, "
            "n.sources = $sources, n.updated_at = datetime() "
            + (
                "SET n.source_confidences = $source_confidences "
                if source_confidences is not None
                else ""
            )
            + "RETURN n.id AS id"
        )
        params: dict[str, Any] = {
            "canonical_name": canonical_name,
            "id": str(uuid.uuid4()),
            "name": name,
            "aliases": aliases,
            "confidence": confidence,
            "sources": sources,
        }
        if source_confidences is not None:
            params["source_confidences"] = source_confidences
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
    source_confidences: list[float] | None = None,
    extracted_by: str = "parser@v1",
) -> None:
    """Crea o actualiza la relación entre dos nodos ya resueltos (por `id`).

    Si la relación fue rechazada a mano (`rejected`, Sprint 9), el MERGE la sigue
    matcheando (mismo patrón: mismo tipo entre los mismos nodos) pero el `WHERE`
    posterior descarta el `SET` — no se resucita ni se le pisa `confidence`. Si
    está `locked` (corrección manual de tipo/confianza), tampoco se pisa la
    confianza; `extracted_by` ya estaba protegido de por sí (solo se fija
    `ON CREATE`, nunca se reescribe en un re-sync). `source_confidences`: mismo
    array paralelo que `merge_node` (doc 04 §5), omitido si no se pasa.
    """
    if not is_valid_relation_type(relation_type):
        raise ValueError(f"Tipo de relación desconocido: {relation_type!r}")
    query = (
        "MATCH (a {id: $source_id}), (b {id: $target_id}) "
        f"MERGE (a)-[r:{relation_type}]->(b) "
        "ON CREATE SET r.id = randomUUID(), r.extracted_by = $extracted_by, "
        "r.extracted_at = datetime(), r.rejected = false, r.locked = false "
        "WITH r WHERE NOT coalesce(r.rejected, false) "
        "SET r.confidence = CASE WHEN coalesce(r.locked, false) "
        "THEN r.confidence ELSE $confidence END, "
        "r.sources = $sources"
        + (", r.source_confidences = $source_confidences" if source_confidences is not None else "")
    )
    params: dict[str, Any] = {
        "source_id": source_id,
        "target_id": target_id,
        "confidence": confidence,
        "sources": sources,
        "extracted_by": extracted_by,
    }
    if source_confidences is not None:
        params["source_confidences"] = source_confidences
    async with driver.session() as session:
        await session.run(query, params)


_NODE_FIELDS = (
    "n.id AS id, labels(n)[0] AS node_type, n.canonical_name AS canonical_name, "
    "n.name AS name, n.aliases AS aliases, n.confidence AS confidence, "
    "n.sources AS sources, coalesce(n.extracted_by, 'parser@v1') AS extracted_by, "
    "coalesce(n.locked, false) AS locked, n.created_at AS created_at, "
    "n.updated_at AS updated_at"
)


async def get_node(driver: AsyncDriver, node_id: str) -> NodeRecord | None:
    """Nodo por id, para `GET /v1/graph/nodes/{id}` (doc 06 §2)."""
    query = f"MATCH (n {{id: $node_id}}) RETURN {_NODE_FIELDS}"
    async with driver.session() as session:
        result = await session.run(query, {"node_id": node_id})
        record = await result.single()
        return NodeRecord(record) if record is not None else None


async def find_node_ids_by_sources(driver: AsyncDriver, doc_ids: list[str]) -> list[str]:
    """Node ids que ya comparten alguna fuente con `doc_ids` — enlace memoria↔grafo
    sin extracción LLM nueva (doc 04 §2, `entities[]` de `kos.memory_learn`,
    decidido 2026-08-13): reusa las `sources[]` que `graph_sync` ya escribió en
    vez de volver a extraer entidades del contenido destilado de la memoria."""
    if not doc_ids:
        return []
    query = "MATCH (n) WHERE any(s IN n.sources WHERE s IN $doc_ids) RETURN DISTINCT n.id AS id"
    async with driver.session() as session:
        result = await session.run(query, {"doc_ids": doc_ids})
        return [record["id"] async for record in result]


class RelationRecord(dict[str, Any]):
    """Fila de relación (id, relation_type, source_id/target_id, confidence, sources,
    extracted_by, extracted_at, rejected)."""

    def __init__(self, record: Any) -> None:
        super().__init__(_normalize_temporals(dict(record)))


class NeighborRecord(dict[str, Any]):
    """Fila de vecindario: la relación + el nodo vecino + la dirección."""

    def __init__(self, record: Any) -> None:
        super().__init__(_normalize_temporals(dict(record)))


async def get_neighborhood(
    driver: AsyncDriver, node_id: str, *, limit: int = 50
) -> list[NeighborRecord]:
    """Relaciones entrantes y salientes de un nodo (vecindario inmediato, doc 06 §2),
    sin las rechazadas a mano (`rejected`)."""
    query = (
        "MATCH (n {id: $node_id}) "
        "CALL { "
        "  WITH n MATCH (n)-[r]->(m) WHERE NOT coalesce(r.rejected, false) "
        "  RETURN r AS rel, m AS neighbor, 'outgoing' AS direction "
        "  UNION "
        "  WITH n MATCH (n)<-[r]-(m) WHERE NOT coalesce(r.rejected, false) "
        "  RETURN r AS rel, m AS neighbor, 'incoming' AS direction "
        "} "
        "RETURN rel.id AS rel_id, type(rel) AS relation_type, "
        "rel.confidence AS rel_confidence, rel.sources AS rel_sources, "
        "coalesce(rel.extracted_by, 'parser@v1') AS rel_extracted_by, "
        "rel.extracted_at AS rel_extracted_at, "
        "coalesce(rel.rejected, false) AS rel_rejected, "
        "neighbor.id AS neighbor_id, labels(neighbor)[0] AS neighbor_type, "
        "neighbor.canonical_name AS neighbor_canonical_name, "
        "neighbor.name AS neighbor_name, neighbor.aliases AS neighbor_aliases, "
        "neighbor.confidence AS neighbor_confidence, neighbor.sources AS neighbor_sources, "
        "coalesce(neighbor.extracted_by, 'parser@v1') AS neighbor_extracted_by, "
        "coalesce(neighbor.locked, false) AS neighbor_locked, direction "
        "LIMIT $limit"
    )
    async with driver.session() as session:
        result = await session.run(query, {"node_id": node_id, "limit": limit})
        return [NeighborRecord(record) async for record in result]


async def find_path(
    driver: AsyncDriver, from_id: str, to_id: str, *, max_hops: int = 4
) -> tuple[list[NodeRecord], list[RelationRecord]] | None:
    """Camino más corto entre dos nodos (doc 06 §2), o None si no hay.

    `max_hops` se interpola (no se parametriza): Cypher no acepta parámetros en
    los límites de un patrón de longitud variable `[*..N]`, igual que
    `node_type`/`relation_type` en el resto del módulo. Se acota en Python antes
    de interpolar, nunca viene de texto libre.
    """
    bounded_hops = min(max(max_hops, 1), 6)
    query = (
        "MATCH (a {id: $from_id}), (b {id: $to_id}) "
        f"MATCH p = shortestPath((a)-[*..{bounded_hops}]-(b)) "
        f"RETURN [n IN nodes(p) | {{"
        "id: n.id, node_type: labels(n)[0], canonical_name: n.canonical_name, "
        "name: n.name, aliases: n.aliases, confidence: n.confidence, "
        "sources: n.sources, extracted_by: coalesce(n.extracted_by, 'parser@v1'), "
        "locked: coalesce(n.locked, false), created_at: n.created_at, "
        "updated_at: n.updated_at}] AS path_nodes, "
        "[r IN relationships(p) | {"
        "id: r.id, relation_type: type(r), source_id: startNode(r).id, "
        "target_id: endNode(r).id, confidence: r.confidence, sources: r.sources, "
        "extracted_by: coalesce(r.extracted_by, 'parser@v1'), extracted_at: r.extracted_at, "
        "rejected: coalesce(r.rejected, false)}] AS path_relations"
    )
    async with driver.session() as session:
        result = await session.run(query, {"from_id": from_id, "to_id": to_id})
        record = await result.single()
        if record is None or record["path_nodes"] is None:
            return None
        nodes = [NodeRecord(n) for n in record["path_nodes"]]
        relations = [RelationRecord(r) for r in record["path_relations"]]
        return nodes, relations


async def list_nodes_by_type(
    driver: AsyncDriver, node_type: str, *, cursor: str | None = None, limit: int = 20
) -> tuple[list[NodeRecord], str | None]:
    """Listado paginado por tipo (a diferencia de `fetch_nodes_by_type`, que trae
    todo sin paginar porque la usa entity resolution internamente)."""
    if not is_valid_node_type(node_type):
        raise ValueError(f"Tipo de nodo desconocido: {node_type!r}")
    query = (
        f"MATCH (n:{node_type}) "
        "WHERE $cursor IS NULL OR n.id > $cursor "
        f"RETURN {_NODE_FIELDS} "
        "ORDER BY n.id LIMIT $limit"
    )
    async with driver.session() as session:
        result = await session.run(query, {"cursor": cursor, "limit": limit})
        rows = [NodeRecord(record) async for record in result]
    next_cursor = rows[-1]["id"] if len(rows) == limit else None
    return rows, next_cursor


async def count_relations(driver: AsyncDriver, node_id: str) -> int:
    """Grado del nodo (relaciones no rechazadas), para priorizar qué revisar."""
    query = (
        "MATCH (n {id: $node_id})-[r]-() WHERE NOT coalesce(r.rejected, false) "
        "RETURN count(r) AS total"
    )
    async with driver.session() as session:
        result = await session.run(query, {"node_id": node_id})
        record = await result.single()
        assert record is not None  # count() siempre devuelve una fila
        return int(record["total"])


async def most_connected_nodes(
    driver: AsyncDriver, *, node_type: str | None = None, limit: int = 10
) -> list[NodeRecord]:
    """Nodos con más relaciones activas, para priorizar correcciones manuales."""
    if node_type is not None and not is_valid_node_type(node_type):
        raise ValueError(f"Tipo de nodo desconocido: {node_type!r}")
    label = f":{node_type}" if node_type is not None else ""
    query = (
        f"MATCH (n{label}) "
        "OPTIONAL MATCH (n)-[r]-() WHERE NOT coalesce(r.rejected, false) "
        f"WITH n, count(r) AS degree "
        f"RETURN {_NODE_FIELDS}, degree "
        "ORDER BY degree DESC LIMIT $limit"
    )
    async with driver.session() as session:
        result = await session.run(query, {"limit": limit})
        return [NodeRecord(record) async for record in result]


async def subgraph_relations(driver: AsyncDriver, node_ids: list[str]) -> list[RelationRecord]:
    """Relaciones activas *entre* los nodos dados (subgrafo inducido, doc 06 §2
    `subgraph`, Sprint 10): a diferencia de `get_neighborhood`, no trae vecinos
    fuera del conjunto — es lo que necesita dibujar el grafo sin que aparezcan
    nodos sueltos que no están en la lista mostrada."""
    if not node_ids:
        return []
    query = (
        "MATCH (a)-[r]->(b) "
        "WHERE a.id IN $node_ids AND b.id IN $node_ids "
        "AND NOT coalesce(r.rejected, false) "
        f"RETURN DISTINCT {_RELATION_FIELDS}"
    )
    async with driver.session() as session:
        result = await session.run(query, {"node_ids": node_ids})
        return [RelationRecord(record) async for record in result]


# doc 02 §4 regla 4: mismo umbral que ya usa la UI para decidir qué mostrar
# (≥0.5) — reusado acá como proxy de "débilmente evidenciado" (Sprint 23,
# doc 11 §4: sin nodo Person/KNOWS real todavía, ver docs/deuda-tecnica.md).
GAP_CONFIDENCE_THRESHOLD = 0.5


async def gaps_by_prerequisite(
    driver: AsyncDriver, *, confidence_threshold: float = GAP_CONFIDENCE_THRESHOLD, limit: int = 20
) -> list[dict[str, Any]]:
    """Candidatos de laguna de conocimiento (doc 11 §4/§5, Sprint 23): nodos que
    son `PREREQUISITE_OF` algo pero cuya propia `confidence` está por debajo del
    umbral de visualización — sin `KNOWS`/`Person` real (deuda documentada,
    docs/deuda-tecnica.md), es el proxy más simple que ya existe en el grafo
    para "esto está poco evidenciado en tu vault"."""
    query = (
        "MATCH (prereq)-[r:PREREQUISITE_OF]->(dependent) "
        "WHERE NOT coalesce(r.rejected, false) "
        "AND coalesce(prereq.confidence, 1.0) < $threshold "
        "WITH prereq, collect(DISTINCT dependent.name) AS blocks "
        "RETURN prereq.id AS node_id, prereq.canonical_name AS canonical_name, "
        "prereq.name AS name, coalesce(prereq.confidence, 1.0) AS confidence, blocks "
        "ORDER BY confidence ASC LIMIT $limit"
    )
    async with driver.session() as session:
        result = await session.run(query, {"threshold": confidence_threshold, "limit": limit})
        return [dict(record) async for record in result]


async def _retire_document_relations(driver: AsyncDriver, doc_id: str) -> int:
    """Saca `doc_id` de `sources[]` de toda relación que lo mencione y recalcula
    `confidence` con lo que sobrevive (doc 04 §5, fórmula decidida 2026-08-13:
    misma que suma una fuente -- `max(confidence base restante) + ALIAS_BOOST x
    (n_restantes - 1)` --, aplicada hacia atrás). `source_confidences[i]` puede
    faltar en datos previos a este sprint: `coalesce(..., r.confidence)` usa la
    confidence agregada como la mejor aproximación disponible para esa fuente.
    Relaciones `locked` no se recalculan (corrección del usuario, inmutable) pero
    sí pierden la fuente. Se borran las que quedan sin ninguna, salvo `locked`
    (sobrevive con `sources` vacío — el usuario ya la validó)."""
    query = (
        "MATCH ()-[r]->() WHERE $doc_id IN coalesce(r.sources, []) "
        "WITH r, [i IN range(0, size(r.sources)-1) "
        "WHERE r.sources[i] <> $doc_id] AS keep_idx "
        "WITH r, "
        "     [i IN keep_idx | r.sources[i]] AS kept_sources, "
        "     [i IN keep_idx | coalesce(r.source_confidences[i], r.confidence, 0.0)] "
        "AS kept_confidences "
        "WITH r, kept_sources, kept_confidences, "
        "     CASE WHEN size(kept_confidences) > 0 "
        "THEN apoc.coll.max(kept_confidences) ELSE 0.0 END AS max_kept "
        "SET r.sources = kept_sources, "
        "    r.source_confidences = kept_confidences, "
        "    r.confidence = CASE "
        "        WHEN coalesce(r.locked, false) OR size(kept_sources) = 0 THEN r.confidence "
        "        WHEN max_kept + $alias_boost * (size(kept_sources) - 1) > 1.0 THEN 1.0 "
        "        ELSE max_kept + $alias_boost * (size(kept_sources) - 1) "
        "        END "
        "WITH r WHERE size(r.sources) = 0 AND NOT coalesce(r.locked, false) "
        "DELETE r RETURN count(*) AS deleted"
    )
    async with driver.session() as session:
        result = await session.run(query, {"doc_id": doc_id, "alias_boost": ALIAS_BOOST})
        record = await result.single()
        assert record is not None  # count() siempre devuelve una fila
        return int(record["deleted"])


async def _retire_document_nodes(driver: AsyncDriver, doc_id: str) -> int:
    """Misma lógica que `_retire_document_relations`, para nodos (recalculo de
    `confidence` incluido, doc 04 §5). `DETACH DELETE` también se lleva cualquier
    relación que quedara apuntando al nodo borrado, aunque esa relación tuviera
    otras fuentes propias — un nodo sin evidencia no puede quedar con relaciones
    colgando (caso límite no visto en la práctica, documentado acá en vez de
    resuelto)."""
    query = (
        "MATCH (n) WHERE $doc_id IN coalesce(n.sources, []) "
        "WITH n, [i IN range(0, size(n.sources)-1) "
        "WHERE n.sources[i] <> $doc_id] AS keep_idx "
        "WITH n, "
        "     [i IN keep_idx | n.sources[i]] AS kept_sources, "
        "     [i IN keep_idx | coalesce(n.source_confidences[i], n.confidence, 0.0)] "
        "AS kept_confidences "
        "WITH n, kept_sources, kept_confidences, "
        "     CASE WHEN size(kept_confidences) > 0 "
        "THEN apoc.coll.max(kept_confidences) ELSE 0.0 END AS max_kept "
        "SET n.sources = kept_sources, "
        "    n.source_confidences = kept_confidences, "
        "    n.confidence = CASE "
        "        WHEN coalesce(n.locked, false) OR size(kept_sources) = 0 THEN n.confidence "
        "        WHEN max_kept + $alias_boost * (size(kept_sources) - 1) > 1.0 THEN 1.0 "
        "        ELSE max_kept + $alias_boost * (size(kept_sources) - 1) "
        "        END "
        "WITH n WHERE size(n.sources) = 0 AND NOT coalesce(n.locked, false) "
        "DETACH DELETE n RETURN count(*) AS deleted"
    )
    async with driver.session() as session:
        result = await session.run(query, {"doc_id": doc_id, "alias_boost": ALIAS_BOOST})
        record = await result.single()
        assert record is not None  # count() siempre devuelve una fila
        return int(record["deleted"])


async def retire_document(driver: AsyncDriver, doc_id: str) -> dict[str, int]:
    """Propaga el tombstone de un documento al grafo (doc 05 §5, doc 06 §3
    `document.deleted`, deuda de Sprint 6 resuelta en Sprint 11): retira `doc_id`
    de `sources[]` en nodos y relaciones, y borra los que quedan sin ninguna
    fuente. Relaciones primero — ver `_retire_document_nodes` para el porqué del
    orden. No recalcula `confidence` de lo que sobrevive con otra fuente (doc 04
    §5 lo pide, pero no hay todavía una fórmula definida de cuánto baja por
    perder una fuente entre varias) — deuda visible, no silenciosa."""
    relations_deleted = await _retire_document_relations(driver, doc_id)
    nodes_deleted = await _retire_document_nodes(driver, doc_id)
    return {"relations_deleted": relations_deleted, "nodes_deleted": nodes_deleted}


async def update_node(
    driver: AsyncDriver,
    node_id: str,
    *,
    canonical_name: str | None = None,
    node_type: str | None = None,
    aliases: list[str] | None = None,
) -> NodeRecord | None:
    """Corrección manual (doc 02 §4 regla 5, doc 06 §2 `PATCH /v1/graph/nodes/{id}`):
    fija `locked`/`extracted_by="user"`/`confidence=1.0`. `None` si el nodo no
    existe. El cambio de tipo mueve la label real vía APOC (`apoc.create.setLabels`,
    ya habilitado en el compose) — Cypher no acepta labels por parámetro.
    """
    if node_type is not None and not is_valid_node_type(node_type):
        raise ValueError(f"Tipo de nodo desconocido: {node_type!r}")
    async with driver.session() as session:
        if node_type is not None:
            await session.run(
                "MATCH (n {id: $node_id}) "
                "CALL apoc.create.setLabels(n, [$node_type]) YIELD node "
                "RETURN node",
                {"node_id": node_id, "node_type": node_type},
            )
        result = await session.run(
            "MATCH (n {id: $node_id}) "
            "SET n.canonical_name = coalesce($canonical_name, n.canonical_name), "
            "n.aliases = coalesce($aliases, n.aliases), "
            "n.confidence = 1.0, n.extracted_by = 'user', n.locked = true, "
            "n.updated_at = datetime() "
            f"RETURN {_NODE_FIELDS}",
            {"node_id": node_id, "canonical_name": canonical_name, "aliases": aliases},
        )
        record = await result.single()
        return NodeRecord(record) if record is not None else None


_RELATION_FIELDS = (
    "r.id AS id, type(r) AS relation_type, startNode(r).id AS source_id, "
    "endNode(r).id AS target_id, r.confidence AS confidence, r.sources AS sources, "
    "coalesce(r.extracted_by, 'parser@v1') AS extracted_by, r.extracted_at AS extracted_at, "
    "coalesce(r.rejected, false) AS rejected"
)


async def update_relation(
    driver: AsyncDriver,
    relation_id: str,
    *,
    relation_type: str | None = None,
    confidence: float | None = None,
) -> RelationRecord | None:
    """Corrección manual de una relación (doc 06 §2 `PATCH /v1/graph/relations/{id}`).

    Neo4j no permite cambiar el tipo de una relación existente: si `relation_type`
    cambia, se borra y se recrea entre los mismos nodos preservando `id` y
    propiedades (`properties(r)`), y recién ahí se aplica la corrección.
    """
    if relation_type is not None and not is_valid_relation_type(relation_type):
        raise ValueError(f"Tipo de relación desconocido: {relation_type!r}")
    async with driver.session() as session:
        if relation_type is not None:
            recreated = await session.run(
                "MATCH (a)-[r {id: $relation_id}]->(b) "
                "WITH a, b, r, properties(r) AS props "
                "DELETE r "
                f"CREATE (a)-[r2:{relation_type}]->(b) "
                "SET r2 = props "
                "RETURN r2.id AS id",
                {"relation_id": relation_id},
            )
            if await recreated.single() is None:
                return None
        result = await session.run(
            "MATCH ()-[r {id: $relation_id}]->() "
            "SET r.confidence = coalesce($confidence, 1.0), "
            "r.extracted_by = 'user', r.locked = true "
            f"RETURN {_RELATION_FIELDS}",
            {"relation_id": relation_id, "confidence": confidence},
        )
        record = await result.single()
        return RelationRecord(record) if record is not None else None


async def reject_relation(driver: AsyncDriver, relation_id: str) -> bool:
    """Rechazo manual (soft delete, doc 06 §2 `DELETE /v1/graph/relations/{id}`):
    no se borra, se marca `rejected` para que el sync no la recree. `False` si
    la relación no existe."""
    query = "MATCH ()-[r {id: $relation_id}]->() SET r.rejected = true RETURN r.id AS id"
    async with driver.session() as session:
        result = await session.run(query, {"relation_id": relation_id})
        record = await result.single()
        return record is not None
