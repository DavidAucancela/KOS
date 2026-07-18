"""Tipos de relación del grafo, ontología v1 (doc 02 §3.2). Ontología cerrada: un
tipo nuevo requiere ADR (doc 02 §4 regla 1). `CONTRADICTS` se declara pero no se usa
activamente todavía (doc 02 §6: llega con `Claim` en Fase 5)."""

from __future__ import annotations

from typing import Final, Literal, get_args

RelationType = Literal[
    "USES",
    "RELATED_TO",
    "AUTHORED_BY",
    "PART_OF",
    "DEPENDS_ON",
    "PREREQUISITE_OF",
    "MENTIONS",
    "KNOWS",
    "CONTRADICTS",
    "SUPERSEDES",
]

RELATION_TYPES: Final[frozenset[str]] = frozenset(get_args(RelationType))

# Propiedades comunes a toda relación (doc 02 §3.2).
COMMON_RELATION_PROPERTIES: Final[tuple[str, ...]] = (
    "confidence",
    "sources",
    "extracted_at",
    "extracted_by",
    "valid_from",
    "valid_to",
)


def is_valid_relation_type(value: str) -> bool:
    """El parser propone relaciones libremente; esto valida contra la ontología cerrada."""
    return value in RELATION_TYPES
