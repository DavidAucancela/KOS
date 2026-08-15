"""Herramienta de búsqueda híbrida: `vector.search` (doc 06 §4, Fase 1). Mismo
mapeo que `/v1/query`/`/v1/search` vía `evidence_from_hit` (Sprint 16)."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_core.schemas.agents import EvidenceRef
from kos_core.storage import search as search_storage


class VectorSearchResult(BaseModel):
    evidence: list[EvidenceRef]


async def _search_core(
    engine: Any,
    embed: Any,
    query: str,
    limit: int,
    doc_type: Literal["content", "template"] | None,
) -> VectorSearchResult:
    [query_embedding] = await embed([query])
    hits = await search_storage.hybrid_search(
        engine, query, query_embedding, limit=limit, doc_type=doc_type
    )
    return VectorSearchResult(evidence=[search_storage.evidence_from_hit(hit) for hit in hits])


def register(server: MCPServer) -> None:
    @server.tool(name="vector.search")
    async def vector_search(
        ctx: Context,
        query: str,
        limit: int = 10,
        doc_type: Literal["content", "template"] | None = None,
    ) -> VectorSearchResult:
        """Búsqueda híbrida (léxica + vectorial + título, RRF) sobre chunks
        (doc 06 §4, doc 08 Sprint 3)."""
        app_ctx = ctx.request_context.lifespan_context
        return await _search_core(
            app_ctx.postgres_engine, app_ctx.embedding_client.embed, query, limit, doc_type
        )
