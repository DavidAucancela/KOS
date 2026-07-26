"""Detección de intención "quiero crear algo, ¿qué plantilla uso?" (Sprint 8).

Heurística determinista por palabras clave, NO clasificación LLM: generaliza el
mismo patrón que ya usaba el comando `/nueva-maquina` (bypass del pipeline fijo
por texto de la query) a intención en lenguaje natural — consistente con la
regla de CLAUDE.md de que el LLM nunca media directamente pre-Fase 4. El
universo de frases de esta intención es acotado; se prefiere una heurística
honesta (como `_confidence_from_hits` en `query_service.py`) sobre una llamada
adicional a Ollama que podría "inventar" que hay intención cuando no la hay.
"""

from __future__ import annotations

import re

# "planilla" es sinónimo regional real de "plantilla" en varios países
# hispanohablantes (no solo un typo) — se trata como alias en todos los
# patrones, no como caso especial.
_T = r"plant?illa"

TEMPLATE_INTENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"qu[ée]\s+{_T}",
        rf"existe\s+(?:alguna|una)\s+{_T}",
        rf"hay\s+(?:alguna|una)\s+{_T}",
        rf"tienes?\s+(?:alguna|una)\s+{_T}",
        rf"{_T}\s+(?:para|de|acorde)",
        r"c[oó]mo\s+creo\s+una\s+nota",
        r"quiero\s+crear\s+(?:información|info|una\s+nota|un\s+proyecto)",
        r"me\s+sirve\s+crear\s+una\s+nueva",
        rf"conviene\s+crear\s+una\s+(?:{_T}|nota)\s+nueva",
        # Órdenes imperativas: "crea/hazme/necesito/dame/genera (una) plantilla"
        rf"(?:crea|creame|cr[eé]ame|hazme|genera|generame|necesito|dame)\s+(?:una\s+|un\s+)?{_T}",
        rf"utilizando\s+una\s+{_T}",
        rf"usando\s+una\s+{_T}",
    )
)


def detect_template_intent(query: str) -> bool:
    """True si la pregunta implica "qué plantilla existe/uso para crear algo"."""
    return any(pattern.search(query) for pattern in TEMPLATE_INTENT_PATTERNS)
