"""Etapa 4: embeddings por chunk (doc 05 §3).

Factory con cliente inyectable: la etapa queda testeable sin Ollama (doc 10 §3).
No forma parte de DEFAULT_STAGES: es una etapa cara y en producción corre por
lotes en la task `kos.embed_document` tras persistir la ingesta.
"""

from __future__ import annotations

from collections.abc import Callable

from kos_core.schemas import ParsedDocument
from kos_workers.pipeline.base import Stage

# Recibe textos y devuelve un vector por texto, en el mismo orden.
EmbedBatch = Callable[[list[str]], list[list[float]]]

DEFAULT_BATCH_SIZE = 16


def make_embedding_stage(embed_batch: EmbedBatch, batch_size: int = DEFAULT_BATCH_SIZE) -> Stage:
    """Construye la etapa que rellena `chunk.embedding` embebiendo en lotes."""

    def embed_chunks(doc: ParsedDocument) -> ParsedDocument:
        if not doc.chunks:
            return doc
        texts = [chunk.text for chunk in doc.chunks]
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            vectors.extend(embed_batch(texts[start : start + batch_size]))
        chunks = [
            chunk.model_copy(update={"embedding": vector})
            for chunk, vector in zip(doc.chunks, vectors, strict=True)
        ]
        return doc.model_copy(update={"chunks": chunks})

    return embed_chunks
