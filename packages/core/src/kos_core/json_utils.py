"""Utilidad compartida por quien pide JSON a un LLM local (s7/s8 en
`apps/workers`, `Planner` en `packages/agents`, Sprint 18): los modelos locales
(ej. llama3.2) suelen envolver la respuesta en fences de markdown
(```` ```json ... ``` ````) aunque el prompt pida "SOLO JSON". Promovido a core
en Sprint 18 porque dos paquetes distintos lo necesitan."""

from __future__ import annotations

import re

# Hallazgo real verificando doc 12 §4 en vivo (2026-08-19): llama3.2 a veces
# agrega una explicación en prosa DESPUÉS del cierre ``` (ej. "Esta relación se
# basa en que..."), pese al prompt pedir "SOLO JSON". El regex anterior
# (`^```...|...```$`) solo pelaba fences anclados al inicio/final de todo el
# string — con prosa después del cierre, el `$` nunca matcheaba, la prosa
# sobrevivía pegada al JSON, y `json.loads` fallaba en silencio (el `try/except`
# de s7/s8 lo trata como "sin entidades/relaciones", descartando resultados
# válidos del LLM). Ahora se busca el bloque fenced y se toma solo su
# contenido, sin importar qué haya antes o después.
_CODE_FENCE_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.IGNORECASE | re.DOTALL)


def strip_code_fence(text: str) -> str:
    """Si el texto trae un bloque ```/```json, devuelve solo su contenido
    (ignora cualquier prosa antes o después del fence); si no hay fence,
    devuelve el texto tal cual, recortado."""
    match = _CODE_FENCE_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()
