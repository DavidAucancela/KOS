"""Implementación por defecto de LLM/embeddings sobre Ollama (ADR-0006)."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from kos_core.config import Settings, get_settings

_DEFAULT_TIMEOUT = 120.0


async def ping(settings: Settings | None = None, *, timeout: float = 3.0) -> None:
    """Falla con excepción si Ollama no responde."""
    settings = settings or get_settings()
    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=timeout) as client:
        response = await client.get("/api/version")
        response.raise_for_status()


class OllamaEmbeddingClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = settings or get_settings()
        self.model = settings.ollama_embedding_model
        self._client = client or httpx.AsyncClient(
            base_url=settings.ollama_base_url, timeout=_DEFAULT_TIMEOUT
        )

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = await self._client.post(
            "/api/embed", json={"model": self.model, "input": list(texts)}
        )
        response.raise_for_status()
        embeddings: list[list[float]] = response.json()["embeddings"]
        return embeddings

    async def aclose(self) -> None:
        await self._client.aclose()


class OllamaLLMClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = settings or get_settings()
        self.model = settings.ollama_llm_model
        self._client = client or httpx.AsyncClient(
            base_url=settings.ollama_base_url, timeout=_DEFAULT_TIMEOUT
        )

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        options: dict[str, float | int] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if system is not None:
            payload["system"] = system
        response = await self._client.post("/api/generate", json=payload)
        response.raise_for_status()
        text: str = response.json()["response"]
        return text

    async def aclose(self) -> None:
        await self._client.aclose()
