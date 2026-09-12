"""Interfaz abstracta de LLM y embeddings (ADR-0006: Ollama por defecto)."""

from kos_core.llm.base import EmbeddingClient, LLMClient
from kos_core.llm.factory import make_embedding_client
from kos_core.llm.ollama import OllamaEmbeddingClient, OllamaLLMClient
from kos_core.llm.openai_compatible import OpenAICompatibleEmbeddingClient

__all__ = [
    "EmbeddingClient",
    "LLMClient",
    "OllamaEmbeddingClient",
    "OllamaLLMClient",
    "OpenAICompatibleEmbeddingClient",
    "make_embedding_client",
]
