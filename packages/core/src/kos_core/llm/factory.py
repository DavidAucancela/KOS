"""Selección del cliente de embeddings (ADR-0008).

El LLM se elige en `apps/api` (doc 15 §1: las implementaciones cloud viven ahí);
los embeddings no pueden, porque la ingesta que los usa corre en los workers.
"""

from __future__ import annotations

import logging

from kos_core.config import Settings, get_settings
from kos_core.llm.base import EmbeddingClient
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.llm.openai_compatible import OpenAICompatibleEmbeddingClient

logger = logging.getLogger(__name__)


def make_embedding_client(settings: Settings | None = None) -> EmbeddingClient:
    """`OllamaEmbeddingClient` por defecto (ADR-0006); endpoint hospedado cuando
    `kos_embedding_provider=openai_compatible` (el despliegue gestionado, donde
    no hay GPU). Si falta `kos_embedding_base_url` se cae a Ollama con aviso en
    vez de romper el arranque."""
    settings = settings or get_settings()
    provider = settings.kos_embedding_provider
    if provider == "ollama":
        return OllamaEmbeddingClient(settings)
    if provider != "openai_compatible":
        logger.warning("proveedor de embeddings desconocido %r; usando Ollama", provider)
        return OllamaEmbeddingClient(settings)
    if not settings.kos_embedding_base_url:
        logger.warning(
            "kos_embedding_provider=openai_compatible pero kos_embedding_base_url vacío; "
            "usando Ollama"
        )
        return OllamaEmbeddingClient(settings)
    return OpenAICompatibleEmbeddingClient(settings)
