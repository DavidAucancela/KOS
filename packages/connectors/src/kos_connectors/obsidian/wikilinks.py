"""Wikilinks ``[[...]]`` y tags ``#tag`` del cuerpo markdown (doc 05 §2)."""

from __future__ import annotations

import re

_WIKILINK = re.compile(r"\[\[([^\[\]]+?)\]\]")

# Un tag es `#palabra` no precedida de letra/número, `#` (encabezados) ni `/`
# (fragmentos de URL). Admite anidado con `/` y caracteres del español.
_TAG = re.compile(r"(?<![\w#/])#([\wáéíóúÁÉÍÓÚñÑüÜ][\wáéíóúÁÉÍÓÚñÑüÜ/-]*)")


def extract_wikilinks(text: str) -> list[str]:
    """``[[Nota]]``, ``[[Nota|alias]]`` y ``[[Nota#sección]]`` → destino "Nota".

    Devuelve destinos únicos en orden de aparición.
    """
    seen: dict[str, None] = {}
    for match in _WIKILINK.finditer(text):
        target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
        if target and target not in seen:
            seen[target] = None
    return list(seen)


def extract_tags(text: str) -> list[str]:
    """Tags ``#tag`` del cuerpo; los encabezados markdown no son tags.

    Devuelve tags únicos (sin ``#``) en orden de aparición.
    """
    seen: dict[str, None] = {}
    for match in _TAG.finditer(text):
        tag = match.group(1)
        if tag not in seen:
            seen[tag] = None
    return list(seen)
