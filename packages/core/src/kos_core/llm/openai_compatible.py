"""Cliente de embeddings sobre un endpoint OpenAI-compatible (ADR-0008).

Vive en `core`, no en `apps/api` como los clientes LLM cloud de doc 15 §1: los
embeddings los necesita **la ingesta**, que corre en `apps/workers` y no puede
importar de `apps/api`. No introduce dependencia nueva — habla HTTP con `httpx`,
que ya es dependencia de `core`, y no arrastra el SDK `openai`.

Sirve para cualquier proveedor con el wire format de OpenAI (Deepinfra,
Together, etc.). El modelo sigue siendo **bge-m3 a 1024 dimensiones**: ADR-0008
lo fija para no re-embeder lo ya indexado, y por eso este cliente falla si el
proveedor devuelve otra dimensión en vez de corromper el índice en silencio.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from kos_core.config import Settings, get_settings
from kos_core.observability import get_tracer

_DEFAULT_TIMEOUT = 120.0
EXPECTED_DIM = 1024
"""Dimensión de bge-m3 (ADR-0002: la columna es `vector(1024)`)."""

_tracer = get_tracer("kos-llm")


class EmbeddingDimensionError(RuntimeError):
    """El proveedor devolvió vectores de otra dimensión: el índice existente y
    el schema (`vector(1024)`) quedarían inservibles. Se falla en vez de
    escribir basura."""


class OpenAICompatibleEmbeddingClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = settings or get_settings()
        self.model = settings.kos_embedding_model
        headers = {}
        if settings.kos_embedding_api_key:
            headers["Authorization"] = f"Bearer {settings.kos_embedding_api_key}"
        self._client = client or httpx.AsyncClient(
            base_url=settings.kos_embedding_base_url.rstrip("/"),
            headers=headers,
            timeout=_DEFAULT_TIMEOUT,
        )

    async def embed(
        self, texts: Sequence[str], *, timeout: float | None = None
    ) -> list[list[float]]:
        with _tracer.start_as_current_span("embeddings.embed") as span:
            span.set_attribute("kos.llm.model", self.model)
            span.set_attribute("kos.llm.input_count", len(texts))
            request_kwargs: dict[str, Any] = {"json": {"model": self.model, "input": list(texts)}}
            if timeout is not None:
                request_kwargs["timeout"] = timeout
            response = await self._client.post("/embeddings", **request_kwargs)
            response.raise_for_status()
            # El orden de `data` no está garantizado por el contrato de OpenAI:
            # cada item trae su `index`, y el Protocol exige devolverlos en el
            # orden de entrada.
            items = sorted(response.json()["data"], key=lambda item: item["index"])
            embeddings: list[list[float]] = [item["embedding"] for item in items]
            if embeddings and len(embeddings[0]) != EXPECTED_DIM:
                raise EmbeddingDimensionError(
                    f"el proveedor devolvió vectores de {len(embeddings[0])} dimensiones; "
                    f"KOS indexa en {EXPECTED_DIM} (bge-m3, ADR-0002). "
                    "Revisa kos_embedding_model."
                )
            return embeddings

    async def aclose(self) -> None:
        await self._client.aclose()
