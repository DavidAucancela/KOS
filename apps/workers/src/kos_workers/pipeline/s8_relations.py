"""Etapa 8 — Relaciones candidatas por LLM, solo entre entidades ya detectadas
(doc 05 §3: "el LLM, solo entre entidades detectadas"). Mismo patrón factory que
`s7_entities.py`; requiere que `doc.entities` ya esté poblado (la etapa 7 corre
antes en `kos.graph_sync`, no hay orden implícito en `DEFAULT_STAGES`)."""

from __future__ import annotations

import json
from collections.abc import Callable

from pydantic import ValidationError

from kos_core.ontology import canonicalize, is_valid_relation_type
from kos_core.schemas import ParsedDocument, RelationCandidate
from kos_workers.pipeline._json_utils import strip_code_fence
from kos_workers.pipeline.base import Stage

DEFAULT_MAX_CHARS = 2000

RELATIONS_SYSTEM = (
    "Eres un asistente que detecta relaciones entre entidades ya identificadas en una "
    "base de conocimiento personal. Solo devuelves relaciones que el texto respalda "
    "explícitamente, nunca inventas."
)

_RELATION_TYPES_HINT = (
    "USES, RELATED_TO, AUTHORED_BY, PART_OF, DEPENDS_ON, PREREQUISITE_OF, MENTIONS, "
    "KNOWS, SUPERSEDES"
)


def build_relations_prompt(
    body: str, entity_names: list[str], *, max_chars: int = DEFAULT_MAX_CHARS
) -> str | None:
    """Prompt de relaciones, o None si no hay contenido o menos de 2 entidades."""
    text = (body or "").strip()
    if not text or len(entity_names) < 2:
        return None
    context = text[: max_chars * 4]
    names = ", ".join(entity_names)
    return (
        f"Estas son las entidades ya detectadas en el documento: {names}.\n"
        f"Tipos de relación válidos: {_RELATION_TYPES_HINT}. "
        'Devuelve SOLO un JSON de la forma [{"source": "...", "relation": "...", '
        '"target": "...", "confidence": 0.0-1.0}], usando ÚNICAMENTE nombres de la '
        "lista de entidades como source/target. Si no hay ninguna relación clara entre "
        "ellas, devuelve [].\n\n"
        f"---\n{context}\n---"
    )


def parse_relations_response(raw_json: str, entity_names: list[str]) -> list[RelationCandidate]:
    """Parsea y valida; tolerante a JSON malformado, tipos inválidos o entidades
    fuera de la lista permitida (source/target deben canonicalizar a una conocida)."""
    known = {canonicalize(name) for name in entity_names}
    try:
        items = json.loads(strip_code_fence(raw_json))
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []

    candidates: list[RelationCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not is_valid_relation_type(str(item.get("relation", ""))):
            continue
        if canonicalize(str(item.get("source", ""))) not in known:
            continue
        if canonicalize(str(item.get("target", ""))) not in known:
            continue
        try:
            candidates.append(RelationCandidate.model_validate(item))
        except ValidationError:
            continue
    return candidates


def make_relations_stage(
    generate: Callable[[str], str], *, max_chars: int = DEFAULT_MAX_CHARS
) -> Stage:
    """Construye la etapa que rellena `relations` llamando a `generate`."""

    def extract(doc: ParsedDocument) -> ParsedDocument:
        entity_names = [entity.name for entity in doc.entities]
        prompt = build_relations_prompt(doc.body or "", entity_names, max_chars=max_chars)
        if prompt is None:
            return doc.model_copy(update={"relations": []})
        relations = parse_relations_response(generate(prompt), entity_names)
        return doc.model_copy(update={"relations": relations})

    return extract
