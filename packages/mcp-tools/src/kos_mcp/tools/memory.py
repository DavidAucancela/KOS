"""Herramientas de memoria: `memory.recall` (lectura) y `memory.store`
(escritura, requiere aprobación — doc 06 §4, Fase 3, `kos_mcp.permissions`).

Un intento de `store` sin `confirm=true` (típicamente un paso `memory`/`store`
elegido por el Planner, `executor.py` lo fuerza siempre a `confirm=False`) no
se pierde: queda como `MemoryProposal` pendiente (`memory_proposals`) para
revisión humana vía `GET/PATCH /v1/memory/proposals` — mitigación del riesgo
documentado en `docs/deuda-tecnica.md`."""

from __future__ import annotations

import uuid
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_core.memory_learn import learn_from_query_answer
from kos_core.schemas.memory import MemoryItem, MemoryType
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_mcp.permissions import ApprovalRequired, gate


class MemoryRecallPage(BaseModel):
    items: list[MemoryItem]
    next_cursor: str | None


class MemoryStoreResult(BaseModel):
    approved: bool
    memory_id: uuid.UUID | None
    message: str
    proposal_id: uuid.UUID | None = None


async def _recall_core(
    engine: Any, type: MemoryType | None, q: str | None, cursor: str | None, limit: int
) -> MemoryRecallPage:
    """Auditoría de memoria (doc 06 §2 `GET /v1/memory?type=&q=`); `q` es
    `ILIKE` sobre `content`, no búsqueda semántica todavía (deuda registrada en
    docs/deuda-tecnica.md — Sprint 21 la cierra)."""
    cursor_uuid = uuid.UUID(cursor) if cursor is not None else None
    items, next_cursor = await postgres_storage.list_memories(
        engine, type=type, q=q, cursor=cursor_uuid, limit=limit
    )
    return MemoryRecallPage(
        items=[MemoryItem.model_validate(item) for item in items],
        next_cursor=str(next_cursor) if next_cursor is not None else None,
    )


async def _store_core(
    engine: Any,
    driver: Any,
    embed: Any,
    *,
    query: str,
    answer: str,
    sources: list[str],
    confidence: float,
    confirm: bool,
    trace_id: str,
) -> MemoryStoreResult:
    try:
        gate(
            "memory.store",
            confirm=confirm,
            trace_id=trace_id,
            description=f"guardar memoria episódica para la consulta {query!r}",
        )
    except ApprovalRequired as exc:
        proposal_id = uuid.uuid4()
        await postgres_storage.insert_memory_proposal(
            engine,
            proposal_id=proposal_id,
            query=query,
            answer=answer,
            sources=sources,
            confidence=confidence,
            trace_id=trace_id,
        )
        return MemoryStoreResult(
            approved=False, memory_id=None, message=str(exc), proposal_id=proposal_id
        )

    async def resolve_entities(doc_ids: list[str]) -> list[str]:
        return await neo4j_storage.find_node_ids_by_sources(driver, doc_ids)

    memory_id = await learn_from_query_answer(
        engine,
        query=query,
        answer=answer,
        sources=sources,
        confidence=confidence,
        embed=embed,
        resolve_entities=resolve_entities,
    )
    return MemoryStoreResult(approved=True, memory_id=memory_id, message="memoria guardada")


def register(server: MCPServer) -> None:
    @server.tool(name="memory.recall")
    async def memory_recall(
        ctx: Context,
        type: MemoryType | None = None,
        q: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> MemoryRecallPage:
        """Auditoría de memoria (doc 06 §2 `GET /v1/memory?type=&q=`)."""
        engine = ctx.request_context.lifespan_context.postgres_engine
        return await _recall_core(engine, type, q, cursor, limit)

    @server.tool(name="memory.store", annotations={"readOnlyHint": False})
    async def memory_store(
        ctx: Context,
        query: str,
        answer: str,
        sources: list[str],
        confidence: float,
        confirm: bool = False,
        trace_id: str | None = None,
    ) -> MemoryStoreResult:
        """Escribe una memoria episódica (doc 04 §3 paso 1), sincrónico
        in-process — devuelve el `memory_id` real de inmediato, a diferencia de
        `kos.memory_learn` (Celery, encolado desde `POST /v1/query`). Requiere
        `confirm=true` (doc 06 §4: escrituras piden aprobación por defecto)."""
        app_ctx = ctx.request_context.lifespan_context
        return await _store_core(
            app_ctx.postgres_engine,
            app_ctx.neo4j_driver,
            app_ctx.embedding_client.embed,
            query=query,
            answer=answer,
            sources=sources,
            confidence=confidence,
            confirm=confirm,
            trace_id=trace_id or str(uuid.uuid4()),
        )
