"""Ontología del grafo como código (doc 02, doc 10 §5): tipos de nodo/relación y
la normalización de nombres para entity resolution (doc 05 §4 paso 1)."""

from __future__ import annotations

import re
import unicodedata

from kos_core.ontology.nodes import NODE_TYPES, NodeType, is_valid_node_type
from kos_core.ontology.relations import RELATION_TYPES, RelationType, is_valid_relation_type

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def canonicalize(name: str) -> str:
    """Normaliza un nombre candidato para deduplicación (doc 05 §4): sin acentos,
    minúsculas, sin espacios/puntuación repetida. `FastAPI` / `fast-api` / `Fast API`
    → `fastapi`."""
    decomposed = unicodedata.normalize("NFKD", name.strip().lower())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_ALNUM_RE.sub("", without_accents)


__all__ = [
    "NODE_TYPES",
    "RELATION_TYPES",
    "NodeType",
    "RelationType",
    "canonicalize",
    "is_valid_node_type",
    "is_valid_relation_type",
]
