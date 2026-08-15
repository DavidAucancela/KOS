"""Rama de decisión "s0": responder a la intención de plantilla sin fabricar (Sprint 8).

Se activa cuando `intent_service.detect_template_intent()` es verdadero. NO pasa
por síntesis LLM libre — a diferencia de `query_service.answer_query()`, aquí la
respuesta es determinística (texto fijo/parametrizado) precisamente para no
repetir el problema que motivó este sprint: el LLM combinando fragmentos de
plantilla y de contenido como si fueran una sola cosa coherente.
"""

from __future__ import annotations

import re
import time

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.services import notes_service
from kos_api.services.intent_service import TEMPLATE_INTENT_PATTERNS
from kos_api.services.query_service import Cost, PlanStep, QueryResult
from kos_core.llm.base import EmbeddingClient
from kos_core.storage import search as search_storage
from kos_core.storage.search import RRF_K, SearchHit, evidence_from_hit

# Umbral inicial conservador (referencia: _TITLE_SIMILARITY_THRESHOLD en
# search.py), a refinar con uso real del vault — ver retro de sprint-08.md.
_CLEAR_MATCH_THRESHOLD = 0.3
_AMBIGUITY_MARGIN = 0.15

_CREAR_NOTA_HINT = "/crear-nota {template} | {folder} | <título de tu nota>"


def _strip_intent_words(query: str) -> str:
    """Quita las frases de intención antes de buscar, para no sesgar el retrieval
    hacia la palabra "plantilla" en vez del tema real (p. ej. "proyecto")."""
    cleaned = query
    for pattern in TEMPLATE_INTENT_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = cleaned.strip(" ¿?¡!.,")
    return cleaned or query


def _normalized_score(hit: SearchHit) -> float:
    """Misma normalización que `query_service._confidence_from_hits` en modo hybrid."""
    max_possible = 2.0 / (RRF_K + 1)
    return max(0.0, min(1.0, hit.score / max_possible))


def _dedupe_by_doc(hits: list[SearchHit]) -> list[SearchHit]:
    seen: set = set()
    unique: list[SearchHit] = []
    for hit in hits:
        if hit.doc_id in seen:
            continue
        seen.add(hit.doc_id)
        unique.append(hit)
    return unique


async def resolve_template_intent(
    engine: AsyncEngine,
    embedder: EmbeddingClient,
    *,
    query: str,
    trace_id: str,
) -> QueryResult:
    """Paso `s0`: busca plantillas candidatas y responde sin pasar por el LLM."""
    started = time.perf_counter()
    plan = [
        PlanStep(id="s0", agent="intent", task="detectar intención de creación de nota"),
    ]

    search_query = _strip_intent_words(query)
    try:
        [query_embedding] = await embedder.embed([search_query])
        hits = await search_storage.hybrid_search(
            engine, search_query, query_embedding, limit=5, doc_type="template"
        )
    except Exception:
        hits = await search_storage.lexical_search(
            engine, search_query, limit=5, doc_type="template"
        )
    candidates = _dedupe_by_doc(hits)

    elapsed_ms = (time.perf_counter() - started) * 1000

    if candidates:
        top = candidates[0]
        top_score = _normalized_score(top) if top.source == "hybrid" else top.score
        second_score = 0.0
        if len(candidates) > 1:
            second = candidates[1]
            second_score = _normalized_score(second) if second.source == "hybrid" else second.score
        is_clear = top_score >= _CLEAR_MATCH_THRESHOLD and (
            len(candidates) == 1 or (top_score - second_score) >= _AMBIGUITY_MARGIN
        )
        if is_clear:
            template_name = re.sub(r"^_Templates/", "", top.source_id or "").removesuffix(".md")
            folder = "<carpeta destino>"
            comando = _CREAR_NOTA_HINT.format(template=template_name, folder=folder)
            answer = (
                f"Sí, ya existe una plantilla para esto: **{top.title or template_name}** [1].\n\n"
                f"¿Quieres que cree una nota nueva a partir de ella? Responde con:\n`{comando}`"
            )
            return QueryResult(
                answer=answer,
                evidence=[evidence_from_hit(top)],
                confidence=1.0,
                plan=plan,
                degraded=False,
                cost=Cost(ms=elapsed_ms),
            )

    templates = await notes_service.list_templates(engine)
    if templates:
        listado = "\n".join(
            f"- {t.title or t.template_name} ({t.template_name})" for t in templates
        )
        answer = (
            "No encontré una plantilla que coincida claramente con lo que describes. "
            "Estas son las plantillas que sí existen en el vault:\n\n"
            f"{listado}\n\n"
            "¿Para qué es lo que quieres crear (un proyecto, una persona, una reunión...)? "
            "Con más detalle puedo decirte cuál te sirve o si conviene crear una nueva."
        )
    else:
        answer = (
            "No encontré ninguna plantilla existente en el vault. Cuéntame más sobre qué "
            "quieres crear y puedo ayudarte a definir una estructura, o puedes crear la "
            "plantilla directamente en `_Templates/` de tu vault."
        )
    return QueryResult(
        answer=answer,
        evidence=[],
        confidence=0.0,
        plan=plan,
        degraded=False,
        cost=Cost(ms=elapsed_ms),
    )
