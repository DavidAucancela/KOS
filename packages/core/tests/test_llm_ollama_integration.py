"""Test de embedding real contra el Ollama local (entregable del Sprint 1).

Corre solo con `-m integration` (requiere Ollama nativo con bge-m3 descargado).
"""

import pytest

from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.storage.postgres import EMBEDDING_DIM

pytestmark = pytest.mark.integration


async def test_embedding_real_con_bge_m3() -> None:
    client = OllamaEmbeddingClient()
    try:
        [vector] = await client.embed(["El conocimiento se conecta, no se apila."])
    finally:
        await client.aclose()
    assert len(vector) == EMBEDDING_DIM
    assert any(value != 0.0 for value in vector)
