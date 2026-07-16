"""Contrato de conector (doc 05 §2): el núcleo no conoce ninguna fuente (ADR-0001).

Un conector NO parsea, NO hace chunking y NO toca bases de datos: solo enumera
documentos (`discover`), los recupera (`fetch`) y, opcionalmente, notifica
cambios (`watch`).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from kos_core.schemas import RawDocument


class SourceRef(BaseModel):
    """Identidad de un documento en su fuente + hash para la ingesta incremental."""

    source_id: str
    uri: str
    content_hash: str
    extra: dict[str, Any] = Field(default_factory=dict)


class ChangeEvent(BaseModel):
    """Cambio detectado en una fuente (doc 05 §5)."""

    type: Literal["created", "modified", "deleted"]
    ref: SourceRef
    occurred_at: datetime


@runtime_checkable
class Connector(Protocol):
    """Interfaz común a todas las fuentes (doc 05 §2)."""

    name: str

    def discover(self) -> Iterator[SourceRef]:
        """Enumera los documentos disponibles en la fuente."""
        ...

    def fetch(self, ref: SourceRef) -> RawDocument:
        """Recupera el contenido original de un documento."""
        ...

    def watch(self) -> Iterator[ChangeEvent]:
        """Cambios en tiempo real; opcional (iterador vacío si no hay soporte)."""
        ...
