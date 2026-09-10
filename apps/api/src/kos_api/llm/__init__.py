"""Ruta cloud (OpenAI) opt-in para Planner y WritingAgent (ADR-0007).

El Protocol `LLMClient` vive en `kos_core.llm.base`; la implementación cloud vive
aquí y no en `packages/core` a propósito: solo la ruta de `/v1/query` la usa, y
los workers de ingesta deben seguir 100% locales sin arrastrar el SDK de OpenAI.
"""

from __future__ import annotations

from kos_api.llm.factory import make_llm_client, make_writing_clients
from kos_api.llm.openai_client import CloudLLMError, OpenAILLMClient

__all__ = ["CloudLLMError", "OpenAILLMClient", "make_llm_client", "make_writing_clients"]
