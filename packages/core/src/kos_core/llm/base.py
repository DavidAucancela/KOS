"""Contratos de LLM y embeddings (doc 10 §5). El resto del sistema depende de
estos Protocol, nunca de una implementación concreta (ADR-0006)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingClient(Protocol):
    async def embed(
        self, texts: Sequence[str], *, timeout: float | None = None
    ) -> list[list[float]]:
        """Devuelve un vector por texto, en el mismo orden. `timeout` (segundos,
        auditoría de cierre v0.5): sin especificar, usa el timeout fijo del
        cliente — pasarlo acopla la llamada real al presupuesto de un
        `AgentRequest.constraints.timeout_s` en vez de quedar desacoplada."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        """Genera una respuesta completa (sin streaming). `timeout` (segundos,
        auditoría de cierre v0.5): sin especificar, usa el timeout fijo del
        cliente (`_DEFAULT_TIMEOUT`, 120s) — pasar el `timeout_s` de un
        `Constraints` acopla la llamada real al presupuesto declarado del plan,
        en vez de que un paso lento pueda tardar hasta 120s pese a un
        presupuesto menor."""
        ...
