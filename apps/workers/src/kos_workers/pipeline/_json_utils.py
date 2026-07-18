"""Utilidad compartida por las etapas que piden JSON al LLM (s7, s8): los modelos
locales (ej. llama3.2) suelen envolver la respuesta en fences de markdown
(```` ```json ... ``` ````) aunque el prompt pida "SOLO JSON"."""

from __future__ import annotations

import re

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def strip_code_fence(text: str) -> str:
    """Quita los fences ```/```json de inicio y fin, si están; deja el resto intacto."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()
