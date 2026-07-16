import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from kos_core.schemas import (
    Chunk,
    ChunkPosition,
    EntityCandidate,
    ParsedDocument,
    RawDocument,
    make_doc_id,
)


def test_make_doc_id_es_estable_y_distingue_conectores() -> None:
    doc_id = make_doc_id("obsidian", "notas/kos.md")
    assert doc_id == make_doc_id("obsidian", "notas/kos.md")
    assert doc_id != make_doc_id("pdf", "notas/kos.md")
    assert doc_id != make_doc_id("obsidian", "notas/otra.md")


def test_raw_document_minimo() -> None:
    raw = RawDocument(
        source_id="notas/kos.md",
        connector="obsidian",
        content="# KOS",
        fetched_at=datetime.now(UTC),
    )
    assert raw.mime_type == "text/markdown"
    assert raw.source_metadata == {}


def test_parsed_document_round_trip_json() -> None:
    doc_id = make_doc_id("obsidian", "notas/kos.md")
    chunk = Chunk(doc_id=doc_id, text="hola", position=ChunkPosition(order=0, start=0, end=4))
    doc = ParsedDocument(
        doc_id=doc_id,
        title="KOS",
        chunks=[chunk],
        entities=[EntityCandidate(name="FastAPI", type="Technology")],
        keywords=["conocimiento"],
    )
    again = ParsedDocument.model_validate_json(doc.model_dump_json())
    assert again == doc


def test_confidence_fuera_de_rango_falla() -> None:
    with pytest.raises(ValidationError):
        ParsedDocument(doc_id=uuid.uuid4(), title="x", confidence=1.5)


def test_chunk_embedding_es_opcional() -> None:
    chunk = Chunk(
        doc_id=uuid.uuid4(),
        text="texto",
        position=ChunkPosition(order=0, start=0, end=5),
    )
    assert chunk.embedding is None
