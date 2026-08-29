"""Casos de uso de propuestas de memoria: listado y aprobar/rechazar
(mitigación del riesgo documentado en `docs/deuda-tecnica.md` — un `memory.store`
elegido por el Planner nunca se auto-aprueba, mismo patrón que
`recommendation_service`)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage import postgres as postgres_storage
from kos_mcp.client import EmbeddedToolCaller


async def list_memory_proposals(
    engine: AsyncEngine, *, status: str | None, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    cursor_uuid = uuid.UUID(cursor) if cursor is not None else None
    items, next_cursor = await postgres_storage.list_memory_proposals(
        engine, status=status, cursor=cursor_uuid, limit=limit
    )
    return items, str(next_cursor) if next_cursor is not None else None


async def resolve_proposal(
    engine: AsyncEngine,
    caller: EmbeddedToolCaller,
    proposal_id: uuid.UUID,
    *,
    status: str,
    reason: str | None,
) -> dict[str, Any] | None:
    """`status="approved"` escribe la memoria de verdad reusando `memory.store`
    (único punto de entrada de escritura, `kos_mcp/tools/memory.py`) con
    `confirm=True` — la aprobación humana real que el Planner nunca puede dar
    por su cuenta. `status="rejected"` solo cierra la propuesta."""
    if status == "approved":
        proposal = await postgres_storage.get_memory_proposal(engine, proposal_id)
        if proposal is None or proposal["status"] != "pending":
            return None
        result = await caller.call_tool(
            "memory.store",
            {
                "query": proposal["query"],
                "answer": proposal["answer"],
                "sources": proposal["sources"],
                "confidence": proposal["confidence"],
                "confirm": True,
                "trace_id": proposal["trace_id"],
            },
        )
        memory_id = uuid.UUID(result["memory_id"]) if result.get("memory_id") else None
        return await postgres_storage.update_memory_proposal_status(
            engine, proposal_id, status="approved", memory_id=memory_id
        )
    return await postgres_storage.update_memory_proposal_status(
        engine, proposal_id, status="rejected", rejected_reason=reason
    )
