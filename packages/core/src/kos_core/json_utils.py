"""Utilidad compartida por quien pide JSON a un LLM local (s7/s8 en
`apps/workers`, `Planner` en `packages/agents`, Sprint 18): los modelos locales
(ej. llama3.2) suelen envolver la respuesta en fences de markdown
(```` ```json ... ``` ````) aunque el prompt pida "SOLO JSON". Promovido a core
en Sprint 18 porque dos paquetes distintos lo necesitan."""

from __future__ import annotations

import re

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def strip_code_fence(text: str) -> str:
    """Quita los fences ```/```json de inicio y fin, si están; deja el resto intacto."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()
