"""Etapa 5 — Resumen con LLM (doc 05 §3).

Factory con la función de generación inyectada: la etapa queda testeable sin
Ollama (doc 10 §3). Etapa cara, fuera de DEFAULT_STAGES; en producción corre en
la task `kos.enrich_document`. `build_summary_prompt` se reutiliza desde la task
para no duplicar el prompt.
"""

from __future__ import annotations

from collections.abc import Callable

from kos_core.schemas import ParsedDocument
from kos_workers.pipeline.base import Stage

DEFAULT_MAX_CHARS = 800

SUMMARY_SYSTEM = (
    "Eres un asistente que resume documentos de una base de conocimiento personal. "
    "Resumes con fidelidad, en español, sin inventar información."
)


def build_summary_prompt(body: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> str | None:
    """Prompt de resumen, o None si no hay contenido que resumir."""
    text = (body or "").strip()
    if not text:
        return None
    context = text[: max_chars * 4]
    return (
        "Resume el siguiente documento en 1 a 3 frases, fiel al contenido y sin "
        "inventar. Devuelve solo el resumen.\n\n"
        f"---\n{context}\n---"
    )


def make_summary_stage(
    generate: Callable[[str], str], *, max_chars: int = DEFAULT_MAX_CHARS
) -> Stage:
    """Construye la etapa que rellena `summary` llamando a `generate`."""

    def summarize(doc: ParsedDocument) -> ParsedDocument:
        prompt = build_summary_prompt(doc.body or "", max_chars=max_chars)
        if prompt is None:
            return doc
        summary = generate(prompt).strip()
        return doc.model_copy(update={"summary": summary})

    return summarize
