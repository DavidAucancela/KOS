"""Etapa 2 — Metadata: título, autor, fechas e idioma desde frontmatter/heurísticas."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from kos_core.schemas import ParsedDocument

_FIRST_HEADING_RE = re.compile(r"^#{1,3}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-záéíóúñü]+")

# Un heading real de sección es corto; una plantilla sin llenar (ej. "## **Título**:
# <frase larga de ejemplo>") no lo es. Por encima de esto, se descarta como título
# (doc 08, Sprint 6 — causa raíz del falso positivo de ranking con notas plantilla).
_MAX_HEADING_TITLE_LEN = 80
_BOLD_ITALIC_RE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

# Marcadores de placeholder de motores de plantillas sin resolver (Templater
# `<% %>`, Jinja/Handlebars `{{ }}`, …): un título que los contiene no es un
# título real, es sintaxis de plantilla sin instanciar (ver docs/sprints/sprint-08.md).
_PLACEHOLDER_RE = re.compile(r"<%|%>|\{\{|\}\}")


def _looks_like_placeholder(text: str) -> bool:
    return bool(_PLACEHOLDER_RE.search(text))


def _clean_heading_text(raw: str) -> str:
    """Quita `**negrita**`/`*cursiva*` y `[[wikilinks]]` (con alias) de un heading."""
    text = _WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), raw)
    text = _BOLD_ITALIC_RE.sub(lambda m: m.group(1) or m.group(2) or "", text)
    return re.sub(r"\s+", " ", text).strip()


# Stopwords mínimas: bastan para distinguir es/en sin dependencias externas.
_ES_STOPWORDS = frozenset(
    [
        "el",
        "la",
        "los",
        "las",
        "de",
        "del",
        "que",
        "y",
        "en",
        "un",
        "una",
        "es",
        "son",
        "por",
        "con",
        "para",
        "se",
        "no",
        "como",
        "más",
        "su",
        "al",
    ]
)
_EN_STOPWORDS = frozenset(
    [
        "the",
        "and",
        "of",
        "to",
        "in",
        "is",
        "that",
        "for",
        "with",
        "as",
        "on",
        "are",
        "this",
        "it",
        "be",
        "by",
        "an",
        "at",
        "from",
        "was",
    ]
)
_MIN_SIGNAL = 2  # apariciones mínimas para declarar idioma


def _frontmatter(doc: ParsedDocument) -> dict[str, Any]:
    raw = doc.source_metadata.get("frontmatter")
    return raw if isinstance(raw, dict) else {}


def _parse_datetime(value: object) -> datetime | None:
    """Acepta datetime, date o str ISO; los valores inválidos se ignoran sin lanzar."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _first_key(data: dict[str, Any], keys: tuple[str, ...]) -> object:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _detect_language(text: str) -> str | None:
    words = _WORD_RE.findall(text.lower())
    if not words:
        return None
    es_hits = sum(1 for word in words if word in _ES_STOPWORDS)
    en_hits = sum(1 for word in words if word in _EN_STOPWORDS)
    if es_hits > en_hits and es_hits >= _MIN_SIGNAL:
        return "es"
    if en_hits > es_hits and en_hits >= _MIN_SIGNAL:
        return "en"
    return None


def extract_metadata(doc: ParsedDocument) -> ParsedDocument:
    """Enriquece título, autor, fechas, idioma y keywords sin mutar la entrada."""
    frontmatter = _frontmatter(doc)
    body = doc.body or ""

    title = doc.title
    fm_title = frontmatter.get("title")
    if isinstance(fm_title, str) and fm_title.strip() and not _looks_like_placeholder(fm_title):
        title = fm_title.strip()
    else:
        heading = _FIRST_HEADING_RE.search(body)
        if heading:
            cleaned = _clean_heading_text(heading.group(1))
            if (
                cleaned
                and len(cleaned) <= _MAX_HEADING_TITLE_LEN
                and not _looks_like_placeholder(cleaned)
            ):
                title = cleaned

    author = doc.author
    fm_author = _first_key(frontmatter, ("author", "autor"))
    if isinstance(fm_author, str) and fm_author.strip():
        author = fm_author.strip()

    created_at = (
        _parse_datetime(_first_key(frontmatter, ("created", "created_at", "date")))
        or doc.created_at
    )
    modified_at = (
        _parse_datetime(_first_key(frontmatter, ("modified", "updated", "modified_at")))
        or doc.modified_at
    )

    keywords = list(doc.keywords)
    fm_tags = frontmatter.get("tags") or []
    if isinstance(fm_tags, str):
        fm_tags = [fm_tags]
    if isinstance(fm_tags, list):
        for tag in fm_tags:
            cleaned = str(tag).strip().lstrip("#")
            if cleaned and cleaned not in keywords:
                keywords.append(cleaned)

    return doc.model_copy(
        update={
            "title": title,
            "author": author,
            "created_at": created_at,
            "modified_at": modified_at,
            "language": _detect_language(body),
            "keywords": keywords,
        }
    )
