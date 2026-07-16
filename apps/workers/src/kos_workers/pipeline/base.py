"""Interfaz de etapas y composición del pipeline (doc 10 §3).

Cada etapa es una función pura `ParsedDocument → ParsedDocument`: no muta la
entrada (usa `model_copy`) y es testeable sin Celery ni bases de datos.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import PurePosixPath

from kos_core.schemas import ParsedDocument, RawDocument, make_doc_id
from kos_workers.pipeline.s1_normalize import normalize
from kos_workers.pipeline.s2_metadata import extract_metadata
from kos_workers.pipeline.s3_chunking import chunk_by_headings

# Se registra al persistir y en los eventos document.parsed (doc 06 §3).
PIPELINE_VERSION = "0.1.0"

Stage = Callable[[ParsedDocument], ParsedDocument]

DEFAULT_STAGES: tuple[Stage, ...] = (normalize, extract_metadata, chunk_by_headings)


def bootstrap(raw: RawDocument) -> ParsedDocument:
    """Siembra el ParsedDocument inicial a partir de lo que entregó el conector."""
    if isinstance(raw.content, bytes):
        body = raw.content.decode("utf-8", errors="replace")
    else:
        body = raw.content
    source_metadata = dict(raw.source_metadata)
    links = [str(link) for link in source_metadata.get("links", [])]
    keywords = [str(tag) for tag in source_metadata.get("tags", [])]
    stem = PurePosixPath(raw.source_id).stem
    return ParsedDocument(
        doc_id=make_doc_id(raw.connector, raw.source_id),
        title=stem or raw.source_id,
        body=body,
        source_metadata=source_metadata,
        links=links,
        keywords=keywords,
    )


def run_pipeline(raw: RawDocument, stages: Sequence[Stage] | None = None) -> ParsedDocument:
    """Ejecuta el pipeline completo: bootstrap + etapas en orden."""
    doc = bootstrap(raw)
    for stage in DEFAULT_STAGES if stages is None else stages:
        doc = stage(doc)
    return doc
