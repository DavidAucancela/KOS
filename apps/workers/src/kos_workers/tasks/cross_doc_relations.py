"""Relaciones cross-documento (doc 12 §4): `s8_relations.py` solo propone
relaciones entre entidades del mismo documento — la causa principal de que el
grafo real quede 85% desconectado (doc 12 §1). Encadenada tras `kos.graph_sync`
(mismo patrón de import diferido que `kos.recommend_from_graph_update`, para
evitar un ciclo de import entre módulos que se registran en `celery_app.py`).

Mismo mecanismo que ya prueba `_run_contradiction_recommendations`
(`tasks/recommend.py`, Sprint 24, doc 11 §4) para un problema estructuralmente
idéntico — comparar contenido entre documentos distintos: candidatos
determinísticos vía banda de similitud pgvector (`similarity_band_chunks`,
excluye el propio documento) + veredicto final de un LLM sobre el texto real
de los dos chunks. La diferencia es qué se le pide al LLM: acá se reutiliza
`build_relations_prompt`/`parse_relations_response` de `s8_relations.py` tal
cual (mismo principio "solo entre entidades ya detectadas"), con una bolsa de
entidades tomada de AMBOS documentos en vez de uno solo.

`chunks.entity_node_ids` (migración 0011) es lo que hace esto posible: qué
nodos de Neo4j salieron de cada chunk, persistido al final de cada
`graph_sync` — sin esto, dado el chunk_id de un documento sincronizado hace
tiempo, no habría forma de saber a qué entidades ya resueltas corresponde
(`EntityCandidate.chunk_ids` es transitorio, se descarta en cada corrida)."""

from __future__ import annotations

import asyncio
from typing import Any

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaLLMClient
from kos_core.ontology import canonicalize
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_core.storage import search as search_storage
from kos_core.storage.postgres import create_engine
from kos_workers.celery_app import app
from kos_workers.pipeline.s8_relations import RELATIONS_SYSTEM, build_relations_prompt
from kos_workers.pipeline.s8_relations import parse_relations_response as parse_relations

# Mismos valores que `CONTRADICTION_SIMILARITY_FLOOR/CEILING` (tasks/recommend.py,
# doc 11 §4) como punto de partida (doc 12 §4 lo deja abierto a calibrar):
# por encima del techo es terreno de "duplicado/mismo contenido" (doc 04 §6);
# por debajo del piso, los chunks ya no comparten tema con claridad.
CROSS_DOC_SIMILARITY_FLOOR = 0.75
CROSS_DOC_SIMILARITY_CEILING = 0.92

# Tope por documento sincronizado (doc 12 §7: costo/latencia de más llamadas
# LLM) — mismo criterio de deuda aceptada que `MAX_CONTRADICTION_SEEDS_PER_RUN`
# (tasks/recommend.py) y `gaps_by_prerequisite` (Sprint 23): un documento con
# más chunks que el tope solo procesa los primeros N en esta corrida.
MAX_CHUNKS_PER_RUN = 30


async def _discover_for_chunk(
    engine: Any, driver: Any, generate: Any, *, own_doc_id: str, chunk_id: str
) -> tuple[bool, int]:
    """Un chunk del documento recién sincronizado: busca un chunk de OTRO
    documento en banda de similitud y, si ambos ya tienen entidades resueltas,
    le pide al LLM relaciones entre esa bolsa combinada. Devuelve
    (se_revisó_un_candidato, relaciones_escritas)."""
    chunk = await postgres_storage.get_chunk(engine, chunk_id)
    if chunk is None or chunk["embedding"] is None:
        return False, 0

    matches = await search_storage.similarity_band_chunks(
        engine,
        chunk["embedding"],
        exclude_doc_id=chunk["doc_id"],
        floor=CROSS_DOC_SIMILARITY_FLOOR,
        ceiling=CROSS_DOC_SIMILARITY_CEILING,
        limit=1,
    )
    if not matches:
        return False, 0
    match = matches[0]

    other = await postgres_storage.get_chunk(engine, match.chunk_id)
    own_node_ids: list[str] = chunk.get("entity_node_ids") or []
    other_node_ids: list[str] = (other.get("entity_node_ids") or []) if other is not None else []
    if not own_node_ids or not other_node_ids:
        return False, 0  # el documento vecino todavía no tiene entidades resueltas

    nodes = await neo4j_storage.fetch_nodes_by_ids(driver, [*own_node_ids, *other_node_ids])
    if len(nodes) < 2:
        return False, 0

    entity_names = [node["name"] for node in nodes]
    prompt = build_relations_prompt(
        f"Fragmento A:\n{chunk['text']}\n\nFragmento B:\n{match.text}", entity_names
    )
    if prompt is None:
        return True, 0
    relations = parse_relations(await generate(prompt), entity_names)

    by_canonical = {canonicalize(node["name"]): node["id"] for node in nodes}
    written = 0
    for relation in relations:
        source_id = by_canonical.get(canonicalize(relation.source))
        target_id = by_canonical.get(canonicalize(relation.target))
        if source_id is None or target_id is None:
            continue  # defensivo: s8 ya restringe a entidades conocidas
        await neo4j_storage.merge_relation(
            driver,
            source_id=source_id,
            relation_type=relation.relation,
            target_id=target_id,
            confidence=relation.confidence,
            sources=sorted({own_doc_id, str(other["doc_id"])})
            if other is not None
            else [own_doc_id],
            source_confidences=[relation.confidence, relation.confidence],
        )
        written += 1
    return True, written


async def _async_discover_cross_document_relations(
    *, doc_id: str, chunk_ids: list[str]
) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    llm = OllamaLLMClient(settings)

    async def generate(prompt: str) -> str:
        return await llm.generate(prompt, system=RELATIONS_SYSTEM)

    try:
        checked = 0
        written = 0
        for chunk_id in chunk_ids[:MAX_CHUNKS_PER_RUN]:
            did_check, relations_written = await _discover_for_chunk(
                engine, driver, generate, own_doc_id=doc_id, chunk_id=chunk_id
            )
            checked += int(did_check)
            written += relations_written
        return {"doc_id": doc_id, "chunks_checked": checked, "relations_written": written}
    finally:
        await llm.aclose()
        await driver.close()
        await engine.dispose()


@app.task(name="kos.discover_cross_document_relations")
def discover_cross_document_relations(*, doc_id: str, chunk_ids: list[str]) -> dict[str, Any]:
    """Encadenada tras `kos.graph_sync` (doc 12 §4) cuando sincronizó al menos
    un chunk. Sin debounce a propósito: corre una vez por documento recién
    sincronizado, no acumula disparos independientes que valga la pena
    agrupar — `merge_relation` ya es idempotente por MERGE (doc 02 §4,
    ADR-0003), así que no hace falta guardarraíl contra re-correr."""
    return asyncio.run(_async_discover_cross_document_relations(doc_id=doc_id, chunk_ids=chunk_ids))
