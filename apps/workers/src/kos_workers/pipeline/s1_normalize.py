"""Etapa 1 — Normalización: texto limpio y estable para el resto del pipeline."""

from __future__ import annotations

import re

from kos_core.schemas import ParsedDocument

# Bloque frontmatter YAML al inicio del cuerpo: ya fue extraído por el conector
# a source_metadata, aquí solo se retira del texto.
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(\n|\Z)", re.DOTALL)
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")


def normalize(doc: ParsedDocument) -> ParsedDocument:
    """Retira el frontmatter, normaliza fines de línea y colapsa líneas en blanco."""
    body = doc.body or ""
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = _FRONTMATTER_RE.sub("", body, count=1)
    body = _EXCESS_BLANK_LINES_RE.sub("\n\n", body)
    body = body.strip()
    return doc.model_copy(update={"body": body})
