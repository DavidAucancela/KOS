"""Etapa 6 — Keywords (doc 05 §3).

Barata y sin LLM: fusiona los keywords sembrados por el conector/frontmatter
con términos frecuentes del cuerpo. Pura y testeable sin infraestructura.
"""

from __future__ import annotations

import re
from collections import Counter

from kos_core.schemas import ParsedDocument

DEFAULT_MAX_KEYWORDS = 12

# Términos de 3+ caracteres (letras acentuadas y dígitos).
_WORD_RE = re.compile(r"[a-záéíóúñü0-9]{3,}")

# Stopwords es/en de alta frecuencia: quitan ruido sin dependencias externas.
_STOPWORDS = frozenset(
    [
        "los",
        "las",
        "del",
        "que",
        "una",
        "unos",
        "unas",
        "por",
        "con",
        "para",
        "como",
        "más",
        "pero",
        "sus",
        "este",
        "esta",
        "estos",
        "estas",
        "son",
        "fue",
        "han",
        "hay",
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "are",
        "was",
        "from",
        "these",
        "those",
        "its",
        "you",
        "your",
        "can",
        "not",
    ]
)


def extract_keywords(
    doc: ParsedDocument, *, max_keywords: int = DEFAULT_MAX_KEYWORDS
) -> ParsedDocument:
    """Combina keywords existentes (primero) con las extraídas por frecuencia."""
    result: list[str] = []
    seen: set[str] = set()
    for keyword in doc.keywords:
        low = keyword.lower()
        if low not in seen:
            seen.add(low)
            result.append(keyword)

    words = _WORD_RE.findall((doc.body or "").lower())
    counts: Counter[str] = Counter()
    first_index: dict[str, int] = {}
    for index, word in enumerate(words):
        if word in _STOPWORDS:
            continue
        counts[word] += 1
        first_index.setdefault(word, index)

    ranked = sorted(counts, key=lambda word: (-counts[word], first_index[word]))
    for word in ranked:
        if len(result) >= max_keywords:
            break
        if word not in seen:
            seen.add(word)
            result.append(word)

    return doc.model_copy(update={"keywords": result[:max_keywords]})
