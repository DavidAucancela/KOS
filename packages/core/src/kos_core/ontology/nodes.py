"""Tipos de nodo del grafo, ontología v1 (doc 02 §3.1). Ontología cerrada: un tipo
nuevo requiere ADR (doc 02 §4 regla 1)."""

from __future__ import annotations

from typing import Final, Literal, get_args

NodeType = Literal[
    "Person",
    "Project",
    "Technology",
    "Concept",
    "Document",
    "Task",
    "Organization",
    "Event",
    "Skill",
]

NODE_TYPES: Final[frozenset[str]] = frozenset(get_args(NodeType))

# Propiedades comunes a todo nodo (doc 02 §3.1): id, canonical_name, aliases,
# created_at/updated_at, confidence, sources, version, extracted_by, locked (Sprint 9).
COMMON_NODE_PROPERTIES: Final[tuple[str, ...]] = (
    "id",
    "canonical_name",
    "aliases",
    "created_at",
    "updated_at",
    "confidence",
    "sources",
    "version",
    "extracted_by",
    "locked",
)


def is_valid_node_type(value: str) -> bool:
    """El parser propone tipos libremente; esto valida contra la ontología cerrada."""
    return value in NODE_TYPES
