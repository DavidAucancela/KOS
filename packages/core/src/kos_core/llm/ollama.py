"""Implementación por defecto de LLM/embeddings sobre Ollama (ADR-0006)."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from kos_core.config import Settings, get_settings
from kos_core.observability import get_tracer

_DEFAULT_TIMEOUT = 120.0
_tracer = get_tracer("kos-llm")


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
        with _tracer.start_as_current_span("ollama.embed") as span:
            span.set_attribute("kos.llm.model", self.model)
            span.set_attribute("kos.llm.input_count", len(texts))
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
        with _tracer.start_as_current_span("ollama.generate") as span:
            span.set_attribute("kos.llm.model", self.model)
            span.set_attribute("kos.llm.temperature", temperature)
            response = await self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            body = response.json()
            if "prompt_eval_count" in body:
                span.set_attribute("kos.llm.prompt_tokens", body["prompt_eval_count"])
            if "eval_count" in body:
                span.set_attribute("kos.llm.completion_tokens", body["eval_count"])
            text: str = body["response"]
            return text

    async def aclose(self) -> None:
        await self._client.aclose()
