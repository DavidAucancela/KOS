"""Renderizado mínimo de plantillas Templater del vault del usuario (doc 06 §4:
creación de notas, versión directa en la API — ver nota en ese doc).

Las plantillas del usuario (`_Templates/*.md`) usan la sintaxis del plugin
Templater de Obsidian: `<% tp.file.title %>`, `<% tp.date.now("YYYY-MM-DD") %>`
y un bloque de comentario `<%* /* ... */ %>` con notas para el humano que no
debe llegar al archivo final. Esta función NO implementa Templater completo
(no evalúa JS): solo sustituye los dos placeholders que sus plantillas reales
usan y limpia el bloque de comentario.
"""

from __future__ import annotations

import re

_COMMENT_BLOCK_RE = re.compile(r"<%\*.*?%>\n?", re.DOTALL)
_TITLE_RE = re.compile(r"<%\s*tp\.file\.title\s*%>")
_DATE_RE = re.compile(r"<%\s*tp\.date\.now\([^)]*\)\s*%>")


def render_template(text: str, *, title: str, date: str) -> str:
    """Sustituye título/fecha y quita el bloque de comentario Templater."""
    rendered = _COMMENT_BLOCK_RE.sub("", text)
    rendered = _TITLE_RE.sub(title, rendered)
    rendered = _DATE_RE.sub(date, rendered)
    return rendered
