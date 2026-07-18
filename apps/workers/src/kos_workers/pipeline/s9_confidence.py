"""Etapa 9 — Confianza por reglas (doc 05 §3). Sin LLM: pura, barata, testeable.

Alcance mínimo de este sprint (Sprint 6): un pequeño ajuste por evidencia extra
dentro del propio documento (más alias detectados = más señal). La acumulación
de confianza entre MÚLTIPLES documentos (doc 02 §4 regla 4) vive en el merge de
Neo4j (`kos.graph_sync`), no aquí — esta etapa solo ve un documento a la vez.
"""

from __future__ import annotations

from kos_core.schemas import ParsedDocument

ALIAS_BOOST = 0.05


def apply_confidence_rules(doc: ParsedDocument) -> ParsedDocument:
    """Sube ligeramente la confianza de entidades con alias detectados (más evidencia)."""
    entities = [
        entity.model_copy(
            update={"confidence": min(1.0, entity.confidence + ALIAS_BOOST * len(entity.aliases))}
        )
        for entity in doc.entities
    ]
    return doc.model_copy(update={"entities": entities})
