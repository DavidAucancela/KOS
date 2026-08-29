"""/v1/memory/proposals — propuestas de `memory.store` elegidas por el
Planner, pendientes de aprobación humana (mitigación del riesgo documentado en
`docs/deuda-tecnica.md`; mismo patrón que `/v1/recommendations`)."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine, tool_caller
from kos_api.services import memory_proposal_service
from kos_core.schemas.memory_proposals import MemoryProposal, MemoryProposalStatus
from kos_mcp.client import EmbeddedToolCaller

router = APIRouter(prefix="/v1/memory/proposals", tags=["memory"])


class MemoryProposalPage(BaseModel):
    items: list[MemoryProposal]
    next_cursor: str | None


class PatchMemoryProposalRequest(BaseModel):
    status: Literal["approved", "rejected"]
    reason: str | None = None


@router.get("", response_model=MemoryProposalPage)
async def list_proposals(
    status: MemoryProposalStatus | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    engine: AsyncEngine = Depends(postgres_engine),
) -> MemoryProposalPage:
    items, next_cursor = await memory_proposal_service.list_memory_proposals(
        engine, status=status, cursor=cursor, limit=limit
    )
    return MemoryProposalPage(
        items=[MemoryProposal.model_validate(item) for item in items], next_cursor=next_cursor
    )


@router.patch("/{proposal_id}", response_model=MemoryProposal)
async def update_proposal(
    proposal_id: uuid.UUID,
    body: PatchMemoryProposalRequest,
    engine: AsyncEngine = Depends(postgres_engine),
    caller: EmbeddedToolCaller = Depends(tool_caller),
) -> MemoryProposal:
    """Aprobar escribe la memoria de verdad (vía `memory.store` con
    `confirm=True`, `memory_proposal_service.resolve_proposal`); rechazar solo
    cierra la propuesta."""
    updated = await memory_proposal_service.resolve_proposal(
        engine, caller, proposal_id, status=body.status, reason=body.reason
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada o ya resuelta")
    return MemoryProposal.model_validate(updated)
