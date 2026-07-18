"""Task de enriquecido (Sprint 4, doc 05 §3): resumen (s5) + keywords (s6).

Etapas caras fuera de la ingesta: `kos.embed_document` encola
`kos.enrich_document`, que rellena `documents.summary` y `documents.keywords`.
Idempotente: si el documento ya tiene resumen y keywords, no rehace nada.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaLLMClient
from kos_core.schemas import ParsedDocument
from kos_core.storage.postgres import chunks_table, create_engine, documents_table
from kos_workers.celery_app import app
from kos_workers.pipeline.s5_summary import SUMMARY_SYSTEM, build_summary_prompt
from kos_workers.pipeline.s6_keywords import extract_keywords
from kos_workers.tasks.graph_sync import graph_sync

# Genera texto a partir de un prompt (LLM real o fake en tests).
AsyncGenerate = Callable[[str], Awaitable[str]]

# (title, summary_existente, keywords_existentes, texto_del_documento)
_Loaded = tuple[str, str | None, list[str], str]


async def _load_document(engine: AsyncEngine, doc_id: uuid.UUID) -> _Loaded | None:
    """Carga título, enriquecido actual y el texto (chunks concatenados)."""
    async with engine.connect() as conn:
        row = (
            (
                await conn.execute(
                    select(
                        documents_table.c.title,
                        documents_table.c.summary,
                        documents_table.c.keywords,
                    ).where(documents_table.c.doc_id == doc_id)
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
    keywords = [str(keyword) for keyword in (row["keywords"] or [])]
    return row["title"] or "", row["summary"], keywords, text


async def _persist_enrichment(
    engine: AsyncEngine, doc_id: uuid.UUID, *, summary: str | None, keywords: list[str]
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            update(documents_table)
            .where(documents_table.c.doc_id == doc_id)
            .values(summary=summary, keywords=keywords)
        )


async def _enrich(
    doc_id: uuid.UUID, *, generate: AsyncGenerate, engine: AsyncEngine
) -> dict[str, Any]:
    """Carga, enriquece y persiste; idempotente. Testeable con generate fake."""
    loaded = await _load_document(engine, doc_id)
    if loaded is None:
        return {"doc_id": str(doc_id), "enriched": False}
    title, existing_summary, existing_keywords, text = loaded
    if existing_summary and existing_keywords:
        return {"doc_id": str(doc_id), "enriched": False}

    doc = ParsedDocument(doc_id=doc_id, title=title, body=text, keywords=existing_keywords)
    doc = extract_keywords(doc)

    prompt = build_summary_prompt(text)
    summary = (await generate(prompt)).strip() if prompt is not None else None

    await _persist_enrichment(engine, doc_id, summary=summary, keywords=doc.keywords)
    return {"doc_id": str(doc_id), "enriched": True, "keywords": len(doc.keywords)}


async def _enrich_document(doc_id: uuid.UUID) -> dict[str, Any]:
    settings = get_settings()
    llm = OllamaLLMClient(settings)
    engine = create_engine(settings)

    async def generate(prompt: str) -> str:
        return await llm.generate(prompt, system=SUMMARY_SYSTEM)

    try:
        return await _enrich(doc_id, generate=generate, engine=engine)
    finally:
        await llm.aclose()
        await engine.dispose()


@app.task(name="kos.enrich_document")
def enrich_document(doc_id: str) -> dict[str, Any]:
    """Rellena resumen y keywords del documento con el LLM local (idempotente)."""
    result = asyncio.run(_enrich_document(uuid.UUID(doc_id)))
    # Etapa cara aparte (Sprint 6, doc 10 §3): entidades/relaciones → grafo.
    # Apagable con KOS_GRAPH_SYNC_ENABLED=false (reingestas masivas, doc 09 §5).
    if get_settings().kos_graph_sync_enabled:
        graph_sync.delay(doc_id)
    return result
