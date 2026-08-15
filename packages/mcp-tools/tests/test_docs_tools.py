"""Tests unitarios de `kos_mcp.tools.docs` (Sprint 16): storage mockeado."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from kos_core.storage import postgres as postgres_module
from kos_mcp.tools import docs as docs_tools

_DOC_ID = uuid.uuid4()

_DOCUMENT = {
    "doc_id": _DOC_ID,
    "title": "FastAPI",
    "summary": "Framework web moderno",
    "connector": "obsidian",
    "source_id": "fastapi.md",
}

_CHUNKS = [
    {"chunk_id": uuid.uuid4(), "text": "Primer chunk", "position": 0},
    {"chunk_id": uuid.uuid4(), "text": "Segundo chunk", "position": 1},
]


async def test_read_document_core_concatena_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_document(engine: Any, doc_id: uuid.UUID) -> dict[str, Any]:
        assert doc_id == _DOC_ID
        return _DOCUMENT

    async def fake_list_chunks(
        engine: Any, doc_id: uuid.UUID, *, cursor: int | None, limit: int
    ) -> tuple[list[dict[str, Any]], int | None]:
        return _CHUNKS, None

    monkeypatch.setattr(postgres_module, "get_document", fake_get_document)
    monkeypatch.setattr(postgres_module, "list_chunks", fake_list_chunks)

    result = await docs_tools._read_document_core(None, str(_DOC_ID), None, 20)

    assert result.title == "FastAPI"
    assert result.text == "Primer chunk\n\nSegundo chunk"
    assert len(result.evidence) == 2
    assert result.next_cursor is None


async def test_read_document_core_lanza_si_no_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_document(engine: Any, doc_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(postgres_module, "get_document", fake_get_document)

    with pytest.raises(ValueError, match="no encontrado"):
        await docs_tools._read_document_core(None, str(uuid.uuid4()), None, 20)
