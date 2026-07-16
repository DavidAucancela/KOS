"""Búsqueda híbrida sobre chunks (Sprint 3, doc 08): léxica + vectorial + RRF.

La léxica (tsvector) responde "¿qué texto contiene esto?"; la vectorial
(pgvector) responde "¿qué texto se parece a esto?" (doc 02 §5). La fusión
Reciprocal Rank Fusion combina ambos rankings sin calibrar scores heterogéneos.

La columna `text_search` es generada (migración 0003) y no está en
`chunks_table`: se consulta con SQL textual.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncEngine

SearchSource = Literal["lexical", "vector", "hybrid"]

RRF_K = 60


class SearchHit(BaseModel):
    """Un chunk recuperado; la evidencia mínima downstream es {doc_id, chunk_id, text}."""

    chunk_id: uuid.UUID
    doc_id: uuid.UUID
    text: str
    score: float
    source: SearchSource
    title: str | None = None
    connector: str | None = None
    source_id: str | None = None
    heading: str | None = None


_LEXICAL_SQL = sql_text(
    """
    SELECT c.chunk_id, c.doc_id, c.text, c.metadata,
           d.title, d.connector, d.source_id,
           ts_rank_cd(c.text_search, websearch_to_tsquery('simple', :query)) AS score
    FROM chunks AS c
    JOIN documents AS d ON d.doc_id = c.doc_id
    WHERE c.text_search @@ websearch_to_tsquery('simple', :query)
    ORDER BY score DESC, c.chunk_id
    LIMIT :limit
    """
)

_VECTOR_SQL = sql_text(
    """
    SELECT c.chunk_id, c.doc_id, c.text, c.metadata,
           d.title, d.connector, d.source_id,
           1 - (c.embedding <=> CAST(:qvec AS vector)) AS score
    FROM chunks AS c
    JOIN documents AS d ON d.doc_id = c.doc_id
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> CAST(:qvec AS vector), c.chunk_id
    LIMIT :limit
    """
)


def _format_vector(values: Sequence[float]) -> str:
    """Literal pgvector: '[v1,v2,...]' (evita registrar adaptadores en SQL textual)."""
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


def _hit_from_row(row: Mapping[Any, Any], *, score: float, source: SearchSource) -> SearchHit:
    metadata = row.get("metadata")
    heading = metadata.get("heading") if isinstance(metadata, dict) else None
    return SearchHit(
        chunk_id=row["chunk_id"],
        doc_id=row["doc_id"],
        text=row["text"],
        score=score,
        source=source,
        title=row.get("title"),
        connector=row.get("connector"),
        source_id=row.get("source_id"),
        heading=heading if isinstance(heading, str) else None,
    )


async def lexical_search(engine: AsyncEngine, query: str, *, limit: int = 20) -> list[SearchHit]:
    """Búsqueda de texto completo con websearch_to_tsquery + ts_rank_cd."""
    async with engine.connect() as conn:
        result = await conn.execute(_LEXICAL_SQL, {"query": query, "limit": limit})
        rows = result.mappings().all()
    return [_hit_from_row(row, score=float(row["score"]), source="lexical") for row in rows]


async def vector_search(
    engine: AsyncEngine, query_embedding: Sequence[float], *, limit: int = 20
) -> list[SearchHit]:
    """Vecinos por distancia coseno sobre chunks con embedding; score = 1 - distancia."""
    params = {"qvec": _format_vector(query_embedding), "limit": limit}
    async with engine.connect() as conn:
        result = await conn.execute(_VECTOR_SQL, params)
        rows = result.mappings().all()
    return [_hit_from_row(row, score=float(row["score"]), source="vector") for row in rows]


def rrf_fuse(
    rankings: Sequence[Sequence[uuid.UUID]], *, k: int = RRF_K
) -> list[tuple[uuid.UUID, float]]:
    """Reciprocal Rank Fusion pura: score(id) = suma de 1/(k + rank_i).

    Orden descendente por score; los empates desempatan por UUID para que el
    resultado sea determinista.
    """
    scores: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], str(pair[0])))


async def hybrid_search(
    engine: AsyncEngine,
    query: str,
    query_embedding: Sequence[float],
    *,
    limit: int = 10,
) -> list[SearchHit]:
    """Léxica y vectorial en paralelo (limit*2 cada una) fusionadas con RRF."""
    lexical, vector = await asyncio.gather(
        lexical_search(engine, query, limit=limit * 2),
        vector_search(engine, query_embedding, limit=limit * 2),
    )
    by_id: dict[uuid.UUID, SearchHit] = {}
    for hit in [*lexical, *vector]:
        by_id.setdefault(hit.chunk_id, hit)

    fused = rrf_fuse(
        [
            [hit.chunk_id for hit in lexical],
            [hit.chunk_id for hit in vector],
        ]
    )
    return [
        by_id[chunk_id].model_copy(update={"score": score, "source": "hybrid"})
        for chunk_id, score in fused[:limit]
    ]
