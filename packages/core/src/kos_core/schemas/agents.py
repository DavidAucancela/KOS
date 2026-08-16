"""Contratos de agentes (doc 06 §3, doc 03).

Se usan desde la Fase 1 aunque el "planner" sea un pipeline fijo (doc 03 §6):
así la extracción a agentes reales en Fase 4 es un refactor, no una reescritura.
La regla de oro (doc 06 §2): una respuesta sin `evidence[]` es un bug.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """Referencia citable. La evidencia mínima es {doc_id, chunk_id, quote};
    node_id/memory_id se rellenan en fases posteriores (grafo, memoria)."""

    doc_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    node_id: uuid.UUID | None = None
    memory_id: uuid.UUID | None = None
    quote: str | None = None
    title: str | None = None
    source_id: str | None = None
    connector: str | None = None
    score: float | None = None
    doc_type: str | None = None


class Constraints(BaseModel):
    """Presupuestos de un paso o plan (doc 03 §3): si se exceden, se degrada.

    Sprint 19 exige `timeout_s`/`max_steps` de verdad (`kos_agents.planner`).
    `max_tokens` sigue sin fuente real de conteo (ningún agente puebla
    `Cost.tokens` desde Ollama todavía) — se acepta pero se ignora hasta que
    exista esa fuente; no-op documentado, no deuda oculta.
    """

    timeout_s: float = 30.0
    max_tokens: int | None = None
    max_steps: int | None = None


class Cost(BaseModel):
    """Coste observado de una ejecución (para trazas y métricas, doc 09 §6)."""

    tokens: int = 0
    ms: float = 0.0


class AgentRequest(BaseModel):
    task: str
    inputs: dict[str, object] = Field(default_factory=dict)
    constraints: Constraints = Field(default_factory=Constraints)
    trace_id: str


class AgentResponse(BaseModel):
    outputs: dict[str, object] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    cost: Cost = Field(default_factory=Cost)
    trace_id: str
