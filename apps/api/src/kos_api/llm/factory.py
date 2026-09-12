"""Selección de proveedor LLM por tarea (ADR-0007).

`kos_<task>_llm_provider` decide entre Ollama (default) y OpenAI. Cuando es
`openai` pero falta la API key, se cae a Ollama con un warning — nunca un fallo
al arrancar. La ruta cloud siempre queda envuelta en `FallbackLLMClient` para
reintentar en local ante error/timeout (soporte offline, ADR-0006).
"""

from __future__ import annotations

import logging
from typing import Literal

from kos_api.llm.openai_client import OpenAILLMClient
from kos_core.config import Settings
from kos_core.llm.base import LLMClient
from kos_core.llm.ollama import OllamaLLMClient

logger = logging.getLogger(__name__)

Task = Literal["planner", "writing"]


class FallbackLLMClient:
    """Intenta `primary`; ante cualquier error usa `fallback`. Implementa el
    Protocol `LLMClient` (ADR-0007: cadena cloud → local)."""

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self._primary = primary
        self._fallback = fallback

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        try:
            return await self._primary.generate(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except Exception as exc:
            logger.warning("cloud LLM falló (%s); reintentando local", exc)
            return await self._fallback.generate(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )

    async def aclose(self) -> None:
        await self._primary.aclose()
        await self._fallback.aclose()


def _cloud_enabled(settings: Settings, provider: str) -> bool:
    if provider == "ollama":
        return False
    if provider != "openai":
        logger.warning("proveedor LLM desconocido %r; usando Ollama", provider)
        return False
    if not settings.openai_api_key:
        logger.warning("proveedor LLM openai pero openai_api_key vacío; usando Ollama")
        return False
    return True


def make_llm_client(settings: Settings, *, task: Task) -> LLMClient:
    """Cliente para el Planner: `FallbackLLMClient(cloud, local)` si cloud está
    habilitado para `task`, si no `OllamaLLMClient`."""
    provider = str(getattr(settings, f"kos_{task}_llm_provider"))
    if not _cloud_enabled(settings, provider):
        return OllamaLLMClient(settings)
    return FallbackLLMClient(OpenAILLMClient(settings, task=task), OllamaLLMClient(settings))


def make_writing_clients(settings: Settings) -> tuple[LLMClient, LLMClient | None]:
    """`(local, cloud_or_none)` para el WritingAgent, que necesita ambos por
    separado: su puerta `cloud_safe` elige por evidencia, no un fallback ciego."""
    local = OllamaLLMClient(settings)
    provider = str(settings.kos_writing_llm_provider)
    if not _cloud_enabled(settings, provider):
        return local, None
    # La ranura cloud se envuelve en FallbackLLMClient: si OpenAI falla en una
    # síntesis ya autorizada (toda la evidencia cloud_safe), se reintenta local
    # en vez de devolver 503 (ADR-0007, cadena de fallback).
    cloud = FallbackLLMClient(OpenAILLMClient(settings, task="writing"), OllamaLLMClient(settings))
    return local, cloud
