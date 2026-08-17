"""Herramienta de recomendaciones: `recommendations.store` (escritura,
Sprint 22, doc 11 §5/§6) — el `RecommenderAgent` la usa para persistir cada
recomendación generada, con el mismo gate de aprobación que `memory.store`
(forzado por el propio agente: el sistema completando un paso ya decidido de
antemano, no un LLM autónomo — doc 11 §5, mismo espíritu que `LearningAgent`)."""

from __future__ import annotations

import uuid
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_core.schemas.recommendations import RecommendationType
from kos_core.storage import postgres as postgres_storage
from kos_mcp.permissions import ApprovalRequired, gate


class RecommendationStoreResult(BaseModel):
    approved: bool
    recommendation_id: uuid.UUID | None
    message: str


async def _store_core(
    engine: Any,
    *,
    type: RecommendationType,
    title: str,
    description: str,
    evidence: list[dict[str, Any]],
    target_entities: list[str],
    confidence: float,
    priority: int,
    source_event_id: str | None,
    confirm: bool,
    trace_id: str,
) -> RecommendationStoreResult:
    try:
        gate(
            "recommendations.store",
            confirm=confirm,
            trace_id=trace_id,
            description=f"crear recomendación {type!r}: {title!r}",
        )
    except ApprovalRequired as exc:
        return RecommendationStoreResult(approved=False, recommendation_id=None, message=str(exc))

    recommendation_id = uuid.uuid4()
    await postgres_storage.insert_recommendation(
        engine,
        recommendation_id=recommendation_id,
        type=type,
        title=title,
        description=description,
        evidence=evidence,
        target_entities=target_entities,
        confidence=confidence,
        priority=priority,
        status="pending",
        source_event_id=source_event_id,
    )
    return RecommendationStoreResult(
        approved=True, recommendation_id=recommendation_id, message="recomendación guardada"
    )


def register(server: MCPServer) -> None:
    @server.tool(name="recommendations.store", annotations={"readOnlyHint": False})
    async def recommendations_store(
        ctx: Context,
        type: RecommendationType,
        title: str,
        description: str = "",
        evidence: list[dict[str, Any]] | None = None,
        target_entities: list[str] | None = None,
        confidence: float = 0.0,
        priority: int = 0,
        source_event_id: str | None = None,
        confirm: bool = False,
        trace_id: str | None = None,
    ) -> RecommendationStoreResult:
        """Escribe una `Recommendation` (doc 11 §2). Requiere `confirm=true`
        (doc 06 §4: escrituras piden aprobación por defecto)."""
        engine = ctx.request_context.lifespan_context.postgres_engine
        return await _store_core(
            engine,
            type=type,
            title=title,
            description=description,
            evidence=evidence or [],
            target_entities=target_entities or [],
            confidence=confidence,
            priority=priority,
            source_event_id=source_event_id,
            confirm=confirm,
            trace_id=trace_id or str(uuid.uuid4()),
        )
