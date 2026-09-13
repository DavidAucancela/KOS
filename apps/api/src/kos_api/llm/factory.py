"""Selección de proveedor LLM (ADR-0007 y ADR-0008).

Dos modos, y el segundo gana cuando está configurado:

1. **Por tarea (ADR-0007, modo local)** — `kos_<task>_llm_provider` elige entre
   Ollama (default) y OpenAI, y la ruta cloud se envuelve en un fallback a local
   para no perder disponibilidad offline.
2. **Cadena de proveedores (ADR-0008, despliegue gestionado)** —
   `KOS_LLM_PROVIDER_CHAIN=openai,openrouter`: se intenta cada proveedor en
   orden. Ahí no hay Ollama que valga como reserva (Railway no tiene GPU), así
   que la cadena es cloud → cloud y, agotada, la petición falla de forma
   visible en vez de degradarse en silencio.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from kos_api.llm.openai_client import OpenAILLMClient
from kos_core.config import Settings
from kos_core.llm.base import LLMClient
from kos_core.llm.ollama import OllamaLLMClient

logger = logging.getLogger(__name__)

Task = Literal["planner", "writing"]


class ChainLLMClient:
    """Intenta cada cliente en orden; propaga el error del último si todos fallan.

    Implementa el Protocol `LLMClient`. Es la generalización del fallback de
    ADR-0007: con dos clientes se comporta igual que antes.
    """

    def __init__(self, clients: list[LLMClient]) -> None:
        if not clients:
            raise ValueError("ChainLLMClient necesita al menos un cliente")
        self._clients = clients

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        last_index = len(self._clients) - 1
        for index, client in enumerate(self._clients):
            try:
                return await client.generate(
                    prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            except Exception as exc:
                if index == last_index:
                    # Sin reserva que quede: el error sube. En el despliegue
                    # gestionado esto es deliberado (ADR-0008).
                    raise
                # El tipo, no solo el mensaje (PR #26): distinguir en el log un
                # fallo permanente (key revocada, modelo inexistente) de uno
                # transitorio (red, 429) antes de probar el siguiente proveedor.
                logger.warning(
                    "proveedor LLM %d/%d falló (%s: %s); probando el siguiente",
                    index + 1,
                    len(self._clients),
                    type(exc).__name__,
                    exc,
                )
        raise AssertionError("inalcanzable")  # pragma: no cover

    async def aclose(self) -> None:
        for client in self._clients:
            await client.aclose()


class FallbackLLMClient(ChainLLMClient):
    """Cadena de dos: `primary` y, ante cualquier error, `fallback` (ADR-0007)."""

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        super().__init__([primary, fallback])


@dataclass(frozen=True)
class _CloudProvider:
    """Cómo construir un proveedor con wire format de OpenAI (ADR-0008)."""

    api_key: str
    base_url: str
    model: str


def _cloud_provider(settings: Settings, name: str) -> _CloudProvider | None:
    """Configuración del proveedor, o None si no es usable (desconocido o sin key)."""
    table = {
        "openai": _CloudProvider(
            settings.openai_api_key, settings.openai_base_url, settings.openai_llm_model
        ),
        "openrouter": _CloudProvider(
            settings.openrouter_api_key,
            settings.openrouter_base_url,
            settings.openrouter_llm_model,
        ),
        "groq": _CloudProvider(
            settings.groq_api_key, settings.groq_base_url, settings.groq_llm_model
        ),
    }
    provider = table.get(name)
    if provider is None:
        logger.warning("proveedor LLM desconocido %r; se omite de la cadena", name)
        return None
    if not provider.api_key:
        logger.warning("proveedor LLM %r sin API key; se omite de la cadena", name)
        return None
    return provider


def _make_chain(settings: Settings, *, task: Task) -> LLMClient | None:
    """Cliente de la cadena `kos_llm_provider_chain`, o None si no se configuró.

    `ollama` se acepta como eslabón explícito para poder probar la cadena en
    local; en el despliegue gestionado no se pone porque no existe ahí.
    """
    names = settings.llm_provider_chain
    if not names:
        return None
    clients: list[LLMClient] = []
    for name in names:
        if name == "ollama":
            clients.append(OllamaLLMClient(settings))
            continue
        provider = _cloud_provider(settings, name)
        if provider is None:
            continue
        clients.append(
            OpenAILLMClient(
                settings,
                task=task,
                model=provider.model,
                base_url=provider.base_url,
                api_key=provider.api_key,
                provider=name,
            )
        )
    if not clients:
        logger.warning(
            "kos_llm_provider_chain=%r no dejó ningún proveedor usable; usando Ollama",
            settings.kos_llm_provider_chain,
        )
        return OllamaLLMClient(settings)
    if len(clients) == 1:
        return clients[0]
    return ChainLLMClient(clients)


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
    """Cadena de ADR-0008 si está configurada; si no, el comportamiento por
    tarea de ADR-0007: `FallbackLLMClient(cloud, local)` u `OllamaLLMClient`."""
    chain = _make_chain(settings, task=task)
    if chain is not None:
        return chain
    provider = str(getattr(settings, f"kos_{task}_llm_provider"))
    if not _cloud_enabled(settings, provider):
        return OllamaLLMClient(settings)
    return FallbackLLMClient(OpenAILLMClient(settings, task=task), OllamaLLMClient(settings))


def make_writing_clients(settings: Settings) -> tuple[LLMClient, LLMClient | None]:
    """`(local, cloud_or_none)` para el WritingAgent, que necesita ambos por
    separado: su puerta `cloud_safe` elige por evidencia, no un fallback ciego.

    Con la cadena de ADR-0008 la ranura cloud es la cadena entera. La ranura
    local sigue siendo Ollama: en el despliegue gestionado no existe, pero
    tampoco debería usarse nunca, porque una fuente `cloud_safe=false` no se
    ingiere allí (ADR-0008). Si aun así llegara evidencia no-cloud_safe —una
    fuente migrada desde local—, la síntesis falla de forma visible en vez de
    mandar a la nube contenido marcado como no apto.
    """
    local = OllamaLLMClient(settings)
    chain = _make_chain(settings, task="writing")
    if chain is not None:
        return local, chain
    provider = str(settings.kos_writing_llm_provider)
    if not _cloud_enabled(settings, provider):
        return local, None
    # La ranura cloud se envuelve en FallbackLLMClient: si OpenAI falla en una
    # síntesis ya autorizada (toda la evidencia cloud_safe), se reintenta local
    # en vez de devolver 503 (ADR-0007, cadena de fallback).
    cloud = FallbackLLMClient(OpenAILLMClient(settings, task="writing"), OllamaLLMClient(settings))
    return local, cloud
