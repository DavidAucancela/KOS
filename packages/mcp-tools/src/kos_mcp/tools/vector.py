"""Herramienta de búsqueda híbrida: `vector.search` (doc 06 §4, Fase 1). Mismo
mapeo que `/v1/query`/`/v1/search` vía `evidence_from_hit` (Sprint 16) y misma
orquestación (modo + degradación + confidence) vía `search_storage.retrieve`
(Sprint 17, promovida desde `_retrieve` de `query_service.py` para que
`RetrievalAgent` reuse esta tool sin perder ese comportamiento)."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_core.schemas.agents import EvidenceRef
from kos_core.storage import search as search_storage
from kos_core.storage.search import SearchMode


class VectorSearchResult(BaseModel):
    evidence: list[EvidenceRef]
    confidence: float
    degraded: bool


async def _search_core(
    engine: Any,
    embed: Any,
    query: str,
    limit: int,
    mode: SearchMode,
    doc_type: str | None,
) -> VectorSearchResult:
    result = await search_storage.retrieve(
        engine, embed, query=query, limit=limit, mode=mode, doc_type=doc_type
    )
    return VectorSearchResult(
        evidence=[search_storage.evidence_from_hit(hit) for hit in result.hits],
        confidence=result.confidence,
        degraded=result.degraded,
    )


def register(server: MCPServer) -> None:
    @server.tool(name="vector.search")
    async def vector_search(
        ctx: Context,
        query: str,
        limit: int = 10,
        mode: SearchMode = "hybrid",
        doc_type: str | None = None,
    ) -> VectorSearchResult:
        """Búsqueda sobre chunks (doc 06 §4, doc 08 Sprint 3): `mode` elige
        lexical/vector/hybrid (RRF); si `vector`/`hybrid` fallan al embeber la
        query, degrada a léxica pura (`degraded=true` en la salida) en vez de
        fallar la búsqueda."""
        app_ctx = ctx.request_context.lifespan_context
        return await _search_core(
            app_ctx.postgres_engine, app_ctx.embedding_client.embed, query, limit, mode, doc_type
        )
