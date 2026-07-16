"""Búsqueda contra la BD local con el mini-vault embebido (Sprint 3).

Requiere: make up, migraciones hasta 0003 y una ingesta con embeddings hecha.
Corre solo con `-m integration`.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.storage.postgres import create_engine
from kos_core.storage.search import hybrid_search, lexical_search, vector_search

pytestmark = pytest.mark.integration


async def _embedded_chunks(engine: AsyncEngine) -> int:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL"))
        return int(result.scalar_one())


async def test_busqueda_lexica_vectorial_e_hibrida() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        if await _embedded_chunks(engine) == 0:
            pytest.skip("no hay chunks con embedding: sincronizar el mini-vault primero")

        lexical = await lexical_search(engine, "contenedores", limit=5)
        assert lexical, "la búsqueda léxica no devolvió resultados"
        assert any("contenedor" in hit.text.lower() for hit in lexical)
        assert all(hit.source == "lexical" for hit in lexical)

        embedder = OllamaEmbeddingClient(settings)
        try:
            [query_embedding] = await embedder.embed(["¿Qué plataforma gestiona contenedores?"])
        finally:
            await embedder.aclose()

        vector = await vector_search(engine, query_embedding, limit=5)
        assert vector, "la búsqueda vectorial no devolvió resultados"
        assert all(hit.score > 0 for hit in vector)

        hybrid = await hybrid_search(engine, "contenedores", query_embedding, limit=5)
        assert hybrid, "la búsqueda híbrida no devolvió resultados"
        assert all(hit.source == "hybrid" for hit in hybrid)
        seen = {hit.chunk_id for hit in lexical} | {hit.chunk_id for hit in vector}
        assert {hit.chunk_id for hit in hybrid} <= seen
    finally:
        await engine.dispose()
