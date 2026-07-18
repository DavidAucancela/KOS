"""Búsqueda híbrida sobre chunks (Sprint 3, doc 08): léxica + vectorial + título + RRF.

La léxica (tsvector) responde "¿qué texto contiene esto?"; la vectorial
(pgvector) responde "¿qué texto se parece a esto?" (doc 02 §5); la de título
(Sprint 5, fix de desambiguación) responde "¿el título de qué documento
coincide con esto?". La fusión Reciprocal Rank Fusion combina los tres
rankings sin calibrar scores heterogéneos.

La columna `text_search` es generada (migración 0003) y no está en
`chunks_table`: se consulta con SQL textual.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncEngine

SearchSource = Literal["lexical", "vector", "title", "hybrid"]

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

_TITLE_SIMILARITY_THRESHOLD = 0.3

_TITLE_SQL = sql_text(
    """
    WITH terms AS (
        SELECT unnest(CAST(:terms AS text[])) AS term
    ),
    doc_scores AS (
        SELECT d.doc_id, MAX(word_similarity(t.term, d.title)) AS score
        FROM documents AS d
        CROSS JOIN terms AS t
        WHERE d.title IS NOT NULL
        GROUP BY d.doc_id
        HAVING MAX(word_similarity(t.term, d.title)) > :threshold
    )
    SELECT c.chunk_id, c.doc_id, c.text, c.metadata,
           d.title, d.connector, d.source_id, ds.score
    FROM doc_scores AS ds
    JOIN documents AS d ON d.doc_id = ds.doc_id
    JOIN LATERAL (
        SELECT * FROM chunks AS c WHERE c.doc_id = d.doc_id ORDER BY c.position ASC LIMIT 1
    ) AS c ON true
    ORDER BY ds.score DESC, c.chunk_id
    LIMIT :limit
    """
)

# Config 'simple' no filtra stopwords ni aplica stemming (doc de la migración
# 0003: vault multilingüe es/en). Eso rompe dos veces la coincidencia por
# título vía tsvector: (1) websearch_to_tsquery ANDaría TODAS las palabras
# vacías de una pregunta natural contra un título corto, y (2) aun quitando esas
# palabras, "conditional" (de la pregunta) y "conditionals" (del título) son
# tokens distintos sin stemming — igual que "comando" vs. "comands" (con
# errata) en otra nota real del vault. Por eso el título se busca con
# `word_similarity` de pg_trgm (ya habilitado, `infra/postgres/init.sql`):
# tolera plural/singular y errores de tipeo por similitud de trigramas, no por
# igualdad de token.
_STOPWORDS = frozenset(
    [
        "a",
        "al",
        "algo",
        "algún",
        "alguna",
        "algunas",
        "alguno",
        "algunos",
        "ante",
        "antes",
        "como",
        "con",
        "cual",
        "cuales",
        "cuál",
        "cuáles",
        "cuando",
        "cuándo",
        "de",
        "del",
        "donde",
        "dónde",
        "el",
        "ella",
        "ellas",
        "ello",
        "ellos",
        "en",
        "es",
        "esa",
        "esas",
        "ese",
        "eso",
        "esos",
        "esta",
        "estas",
        "este",
        "esto",
        "estos",
        "la",
        "las",
        "lo",
        "los",
        "mi",
        "mis",
        "mí",
        "nota",
        "notas",
        "o",
        "para",
        "pero",
        "por",
        "qué",
        "que",
        "quien",
        "quién",
        "quienes",
        "según",
        "ser",
        "si",
        "sí",
        "su",
        "sus",
        "también",
        "tu",
        "un",
        "una",
        "unas",
        "uno",
        "unos",
        "y",
        "ya",
        "an",
        "and",
        "are",
        "at",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "my",
        "notes",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whose",
    ]
)


def _title_query_terms(query: str) -> list[str]:
    """Palabras significativas de la query (sin vacías), una por término de trigrama."""
    words = re.findall(r"\w+", query.lower(), flags=re.UNICODE)
    return [word for word in words if len(word) > 2 and word not in _STOPWORDS]


def _pg_text_array(values: Sequence[str]) -> str:
    """Literal `text[]` de Postgres: los términos vienen de `\\w+`, sin comas/llaves."""
    return "{" + ",".join(values) + "}"


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


async def title_search(engine: AsyncEngine, query: str, *, limit: int = 20) -> list[SearchHit]:
    """Documentos cuyo título coincide con la query; un chunk representativo por doc.

    Señal de desambiguación (doc 08, Sprint 5): un match léxico genérico en el
    cuerpo de un chunk no distingue "Zero Conditional" de "Zero Trust", pero el
    título sí. Se fusiona como tercera rama de RRF, no como boost aritmético del
    score léxico (evita calibrar scores heterogéneos, contra el diseño del
    archivo).

    A diferencia de `lexical_search`, no usa tsvector/tsquery (rompe con plurales
    y errores de tipeo, ver comentario sobre `_TITLE_SQL`): compara por
    similitud de trigramas (`word_similarity`, pg_trgm) las palabras
    significativas de la query contra el título completo.
    """
    terms = _title_query_terms(query)
    if not terms:
        return []
    params = {
        "terms": _pg_text_array(terms),
        "threshold": _TITLE_SIMILARITY_THRESHOLD,
        "limit": limit,
    }
    async with engine.connect() as conn:
        result = await conn.execute(_TITLE_SQL, params)
        rows = result.mappings().all()
    return [_hit_from_row(row, score=float(row["score"]), source="title") for row in rows]


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
    """Léxica, vectorial y por título en paralelo (limit*2 cada una) fusionadas con RRF."""
    lexical, vector, title = await asyncio.gather(
        lexical_search(engine, query, limit=limit * 2),
        vector_search(engine, query_embedding, limit=limit * 2),
        title_search(engine, query, limit=limit * 2),
    )
    by_id: dict[uuid.UUID, SearchHit] = {}
    for hit in [*lexical, *vector, *title]:
        by_id.setdefault(hit.chunk_id, hit)

    fused = rrf_fuse(
        [
            [hit.chunk_id for hit in lexical],
            [hit.chunk_id for hit in vector],
            [hit.chunk_id for hit in title],
        ]
    )
    return [
        by_id[chunk_id].model_copy(update={"score": score, "source": "hybrid"})
        for chunk_id, score in fused[:limit]
    ]
