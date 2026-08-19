"""Task de sincronización al grafo (Sprint 6, doc 05 §3-4): `document.parsed` → Neo4j.

Encadenada tras `kos.enrich_document` (mismo patrón de encadenado que
`kos.embed_document` → `kos.enrich_document`, ver `tasks/embed.py`/`tasks/enrich.py`).
Corre s7 (entidades) → s8 (relaciones) → s9 (confianza) llamando al LLM real de
forma directamente asíncrona (igual que `tasks/enrich.py` hace con el resumen: no
pasa por el factory `make_X_stage`, que es sync y solo existe para tests/pipeline
puro — aquí se reutilizan `build_*_prompt`/`parse_*_response` directamente).

Entity resolution (doc 05 §4, 5 pasos) resuelve cada entidad candidata contra lo
que ya existe en Neo4j y persiste con `kos_core.storage.neo4j`. Idempotente por
diseño de MERGE (doc 02 §4, ADR-0003): re-correr el mismo documento re-mergea los
mismos nodos/relaciones (el doc_id se une a `sources`, no se duplica).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient, OllamaLLMClient
from kos_core.ontology import canonicalize
from kos_core.schemas import EntityCandidate, ParsedDocument, RelationCandidate
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage.postgres import (
    chunks_table,
    create_engine,
    documents_table,
    similar_nodes,
    upsert_node_embedding,
)
from kos_workers.celery_app import app
from kos_workers.pipeline.s7_entities import ENTITIES_SYSTEM, build_entities_prompt
from kos_workers.pipeline.s7_entities import parse_entities_response as parse_entities
from kos_workers.pipeline.s8_relations import RELATIONS_SYSTEM, build_relations_prompt
from kos_workers.pipeline.s8_relations import parse_relations_response as parse_relations
from kos_workers.pipeline.s9_confidence import ALIAS_BOOST, apply_confidence_rules

# Banda amplia para generar candidatos (doc 12 §3) — el veredicto final lo da
# el LLM (`merge_verdict`), no este score solo; reemplaza el umbral único
# `SIMILARITY_THRESHOLD = 0.9` que antes filtraba paráfrasis razonables antes
# de siquiera llegar al veredicto.
SIMILARITY_CANDIDATE_FLOOR = 0.75

AsyncGenerate = Callable[[str], Awaitable[str]]
AsyncEmbed = Callable[[list[str]], Awaitable[list[list[float]]]]
MergeVerdict = Callable[[str, str], Awaitable[bool]]


async def _load_document_text(engine: AsyncEngine, doc_id: uuid.UUID) -> tuple[str, str] | None:
    """(title, texto concatenado de los chunks) — igual que `tasks/enrich.py`."""
    async with engine.connect() as conn:
        row = (
            (
                await conn.execute(
                    select(documents_table.c.title).where(documents_table.c.doc_id == doc_id)
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        chunk_rows = (
            await conn.execute(
                select(chunks_table.c.text)
                .where(chunks_table.c.doc_id == doc_id)
                .order_by(chunks_table.c.position)
            )
        ).all()
    text = "\n\n".join(chunk_row.text for chunk_row in chunk_rows)
    return row["title"] or "", text


async def _default_merge_verdict(generate: AsyncGenerate, name_a: str, name_b: str) -> bool:
    """Veredicto del LLM para similitud >0.9 pero sin match exacto (doc 05 §4 paso 3)."""
    prompt = (
        f'¿"{name_a}" y "{name_b}" se refieren a la misma entidad? Responde SOLO '
        'JSON: {"same": true} o {"same": false}.'
    )
    try:
        data = json.loads(await generate(prompt))
        return bool(data.get("same", False))
    except (json.JSONDecodeError, AttributeError):
        return False  # ambiguo → no fusionar (más seguro que un merge incorrecto)


def _merge_sources(existing: list[str] | None, doc_id: str) -> list[str]:
    return sorted({*(existing or []), doc_id})


def _merge_source_confidences(
    existing_sources: list[str] | None,
    existing_source_confidences: list[float] | None,
    fallback_confidence: float,
    doc_id: str,
    confidence: float,
) -> list[float]:
    """Array paralelo a `_merge_sources` (doc 04 §5, decidido 2026-08-13): la
    confidence "cruda" con la que se agregó cada fuente, para poder recalcular
    al perder una. Si una fuente previa no tiene su propia entrada (datos de
    antes de este sprint), usa `fallback_confidence` (la confidence agregada del
    nodo) como mejor aproximación disponible."""
    pairs = {
        source: (
            existing_source_confidences[i]
            if existing_source_confidences is not None and i < len(existing_source_confidences)
            else fallback_confidence
        )
        for i, source in enumerate(existing_sources or [])
    }
    pairs[doc_id] = confidence
    return [pairs[source] for source in sorted(pairs)]


def _merge_aliases(existing: list[str] | None, entity: EntityCandidate) -> list[str]:
    return sorted({*(existing or []), *entity.aliases, entity.name})


def _boosted_confidence(existing: float | None, entity: EntityCandidate) -> float:
    """Doc 02 §4 regla 4: cada nueva mención sube la confianza del nodo."""
    return min(1.0, max(existing or 0.0, entity.confidence) + ALIAS_BOOST)


async def _merge_with_candidate(
    driver: Any, candidate: dict[str, Any], entity: EntityCandidate, *, doc_id: str
) -> str:
    return await neo4j_storage.merge_node(
        driver,
        node_type=entity.type,
        canonical_name=candidate["canonical_name"],
        name=candidate.get("name") or entity.name,
        aliases=_merge_aliases(candidate.get("aliases"), entity),
        confidence=_boosted_confidence(candidate.get("confidence"), entity),
        sources=_merge_sources(candidate.get("sources"), doc_id),
        source_confidences=_merge_source_confidences(
            candidate.get("sources"),
            candidate.get("source_confidences"),
            candidate.get("confidence") or 0.0,
            doc_id,
            entity.confidence,
        ),
    )


async def _resolve_entity(
    driver: Any,
    entity: EntityCandidate,
    *,
    doc_id: str,
    engine: AsyncEngine,
    embed: AsyncEmbed,
    merge_verdict: MergeVerdict,
) -> str:
    """Entity resolution (doc 05 §4, doc 12 §3). Paso 2 (match exacto) sigue
    igual; paso 3 (similitud) ahora es una búsqueda ANN indexada contra
    `node_embeddings` (doc 12 §3) en vez de traer todos los nodos del tipo y
    calcular coseno en memoria — el veredicto sigue siendo del LLM, no del
    score de similitud solo."""
    canonical = canonicalize(entity.name)
    [vector] = await embed([entity.name])

    # Paso 2: match exacto por canonical_name + tipo (barato, un solo nodo).
    exact = await neo4j_storage.fetch_node_by_canonical_name(driver, entity.type, canonical)
    if exact is not None:
        node_id = await _merge_with_candidate(driver, exact, entity, doc_id=doc_id)
    else:
        # Paso 3: candidatos por ANN (banda amplia) → veredicto del LLM decide.
        # `node_embeddings` solo indexa canonical_name/embedding — el nodo
        # completo (aliases/confidence/sources) se vuelve a pedir a Neo4j,
        # que sigue siendo la fuente de verdad (ADR-0003).
        candidates = await similar_nodes(
            engine, vector, node_type=entity.type, floor=SIMILARITY_CANDIDATE_FLOOR
        )
        matched = None
        for candidate in candidates:
            full = await neo4j_storage.fetch_node_by_canonical_name(
                driver, entity.type, candidate["canonical_name"]
            )
            if full is None:
                continue  # índice desincronizado (nodo borrado tras el último embed)
            candidate_name = full.get("name") or full["canonical_name"]
            if await merge_verdict(entity.name, candidate_name):
                matched = full
                break

        if matched is not None:
            node_id = await _merge_with_candidate(driver, matched, entity, doc_id=doc_id)
        else:
            # Paso 4: sin match — nodo nuevo con la evidencia de este documento.
            node_id = await neo4j_storage.merge_node(
                driver,
                node_type=entity.type,
                canonical_name=canonical,
                name=entity.name,
                aliases=list(dict.fromkeys(entity.aliases)),
                confidence=entity.confidence,
                sources=[doc_id],
                source_confidences=[entity.confidence],
            )

    await upsert_node_embedding(
        engine,
        node_id=node_id,
        canonical_name=canonical,
        node_type=entity.type,
        embedding=vector,
    )
    return node_id


async def _sync_relations(
    driver: Any, relations: list[RelationCandidate], node_ids: dict[str, str], doc_id: str
) -> int:
    written = 0
    for relation in relations:
        source_id = node_ids.get(canonicalize(relation.source))
        target_id = node_ids.get(canonicalize(relation.target))
        if source_id is None or target_id is None:
            continue  # defensivo: s8 ya restringe a entidades conocidas
        await neo4j_storage.merge_relation(
            driver,
            source_id=source_id,
            relation_type=relation.relation,
            target_id=target_id,
            confidence=relation.confidence,
            sources=[doc_id],
            source_confidences=[relation.confidence],
        )
        written += 1
    return written


async def _extract_entities_and_relations(
    text: str, *, generate_entities: AsyncGenerate, generate_relations: AsyncGenerate
) -> tuple[list[EntityCandidate], list[RelationCandidate]]:
    """s7 → s8, llamando al LLM directamente (mismo estilo que `tasks/enrich.py`)."""
    entities_prompt = build_entities_prompt(text)
    entities = (
        parse_entities(await generate_entities(entities_prompt))
        if entities_prompt is not None
        else []
    )

    entity_names = [entity.name for entity in entities]
    relations_prompt = build_relations_prompt(text, entity_names)
    relations = (
        parse_relations(await generate_relations(relations_prompt), entity_names)
        if relations_prompt is not None
        else []
    )
    return entities, relations


async def _sync_graph(
    doc_id: uuid.UUID,
    *,
    engine: AsyncEngine,
    driver: Any,
    generate_entities: AsyncGenerate,
    generate_relations: AsyncGenerate,
    embed: AsyncEmbed,
    merge_verdict: MergeVerdict,
) -> dict[str, Any]:
    """Núcleo testeable con fakes (engine/driver/LLM inyectados)."""
    loaded = await _load_document_text(engine, doc_id)
    if loaded is None:
        return {"doc_id": str(doc_id), "synced": False}
    _title, text = loaded

    entities, relations = await _extract_entities_and_relations(
        text, generate_entities=generate_entities, generate_relations=generate_relations
    )
    # s9: boost por alias ya aplicado en _resolve_entity/_boosted_confidence al
    # fusionar con lo existente; aquí solo se normalizan las candidatas nuevas.
    normalized = apply_confidence_rules(
        ParsedDocument(doc_id=doc_id, title=_title, entities=entities)
    ).entities

    node_ids: dict[str, str] = {}
    for entity in normalized:
        node_ids[canonicalize(entity.name)] = await _resolve_entity(
            driver,
            entity,
            doc_id=str(doc_id),
            engine=engine,
            embed=embed,
            merge_verdict=merge_verdict,
        )

    relations_written = await _sync_relations(driver, relations, node_ids, str(doc_id))
    return {
        "doc_id": str(doc_id),
        "synced": True,
        "entities": len(normalized),
        "relations": relations_written,
        "node_ids": list(node_ids.values()),
    }


async def _async_graph_sync(doc_id: uuid.UUID) -> dict[str, Any]:
    settings = get_settings()
    llm = OllamaLLMClient(settings)
    embedder = OllamaEmbeddingClient(settings)
    engine = create_engine(settings)
    driver = neo4j_storage.create_driver(settings)

    async def generate_entities(prompt: str) -> str:
        return await llm.generate(prompt, system=ENTITIES_SYSTEM)

    async def generate_relations(prompt: str) -> str:
        return await llm.generate(prompt, system=RELATIONS_SYSTEM)

    async def embed(texts: list[str]) -> list[list[float]]:
        return await embedder.embed(texts)

    async def merge_verdict(name_a: str, name_b: str) -> bool:
        return await _default_merge_verdict(generate_entities, name_a, name_b)

    try:
        return await _sync_graph(
            doc_id,
            engine=engine,
            driver=driver,
            generate_entities=generate_entities,
            generate_relations=generate_relations,
            embed=embed,
            merge_verdict=merge_verdict,
        )
    finally:
        await llm.aclose()
        await embedder.aclose()
        await driver.close()
        await engine.dispose()


@app.task(name="kos.graph_sync")
def graph_sync(doc_id: str) -> dict[str, Any]:
    """Extrae entidades/relaciones y las sincroniza a Neo4j (idempotente por MERGE).

    Encadena `kos.recommend_from_graph_update` (Sprint 22, doc 11 §3) cuando
    sincronizó algo real: hasta este sprint, `GraphUpdated` solo se emitía
    desde correcciones manuales de grafo — el camino automático (esta task)
    nunca lo disparaba pese a que su propio docstring lo prometía
    (`kos_core.schemas.events.GraphUpdated`)."""
    result = asyncio.run(_async_graph_sync(uuid.UUID(doc_id)))
    if result.get("synced") and result.get("node_ids"):
        # Import diferido: evita un ciclo de import a nivel de módulo entre
        # graph_sync.py y recommend.py (ambos se registran en celery_app.py).
        from kos_workers.tasks.recommend import recommend_from_graph_update

        recommend_from_graph_update.delay(node_ids=result["node_ids"], relation_ids=[])
    return result
