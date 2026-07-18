"""Etapa 7 — Entidades candidatas por LLM, validadas contra la ontología (doc 05 §3).

Mismo patrón que `s5_summary.py`: factory con la función de generación inyectada,
testeable sin Ollama. La salida del LLM se pide en JSON y se valida contra
`EntityCandidate` + los tipos de nodo de `kos_core.ontology`; lo que no valida se
descarta silenciosamente (un documento raro no debe tumbar el pipeline, doc 06 §2
"la evidencia manda" aplicado también aquí: mejor sin esa entidad que inventada).

Simplificación de este sprint: la extracción corre sobre el documento completo (no
por chunk), así que `chunk_ids` queda vacío aquí — la evidencia primaria es el
`doc_id` (asignado por la task `kos.graph_sync`, no por esta etapa pura).
"""

from __future__ import annotations

import json
from collections.abc import Callable

from pydantic import ValidationError

from kos_core.ontology import is_valid_node_type
from kos_core.schemas import EntityCandidate, ParsedDocument
from kos_workers.pipeline._json_utils import strip_code_fence
from kos_workers.pipeline.base import Stage

DEFAULT_MAX_CHARS = 2000

ENTITIES_SYSTEM = (
    "Eres un asistente que extrae entidades de una base de conocimiento personal. "
    "Solo devuelves lo que el texto respalda explícitamente, nunca inventas."
)

_NODE_TYPES_HINT = (
    "Person, Project, Technology, Concept, Document, Task, Organization, Event, Skill"
)


def build_entities_prompt(body: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> str | None:
    """Prompt de extracción de entidades, o None si no hay contenido."""
    text = (body or "").strip()
    if not text:
        return None
    context = text[: max_chars * 4]
    return (
        "Extrae las entidades mencionadas en el siguiente documento. Tipos válidos: "
        f"{_NODE_TYPES_HINT}. Devuelve SOLO un JSON de la forma "
        '[{"name": "...", "type": "...", "aliases": [], "confidence": 0.0-1.0}]. '
        "Si no hay ninguna entidad clara, devuelve [].\n\n"
        f"---\n{context}\n---"
    )


def parse_entities_response(raw_json: str) -> list[EntityCandidate]:
    """Parsea y valida la respuesta del LLM; tolerante a JSON malformado o tipos inválidos."""
    try:
        items = json.loads(strip_code_fence(raw_json))
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []

    candidates: list[EntityCandidate] = []
    for item in items:
        if not isinstance(item, dict) or not is_valid_node_type(str(item.get("type", ""))):
            continue
        try:
            candidates.append(EntityCandidate.model_validate(item))
        except ValidationError:
            continue
    return candidates


def make_entities_stage(
    generate: Callable[[str], str], *, max_chars: int = DEFAULT_MAX_CHARS
) -> Stage:
    """Construye la etapa que rellena `entities` llamando a `generate`."""

    def extract(doc: ParsedDocument) -> ParsedDocument:
        prompt = build_entities_prompt(doc.body or "", max_chars=max_chars)
        if prompt is None:
            return doc
        entities = parse_entities_response(generate(prompt))
        return doc.model_copy(update={"entities": entities})

    return extract
