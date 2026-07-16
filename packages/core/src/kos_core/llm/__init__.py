"""Interfaz abstracta de LLM y embeddings (ADR-0006: Ollama por defecto)."""

from kos_core.llm.base import EmbeddingClient, LLMClient
from kos_core.llm.ollama import OllamaEmbeddingClient, OllamaLLMClient

__all__ = ["EmbeddingClient", "LLMClient", "OllamaEmbeddingClient", "OllamaLLMClient"]
