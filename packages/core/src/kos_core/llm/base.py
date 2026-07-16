"""Contratos de LLM y embeddings (doc 10 §5). El resto del sistema depende de
estos Protocol, nunca de una implementación concreta (ADR-0006)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingClient(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Devuelve un vector por texto, en el mismo orden."""
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
    ) -> str:
        """Genera una respuesta completa (sin streaming)."""
        ...
