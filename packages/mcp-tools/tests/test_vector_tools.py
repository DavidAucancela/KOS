"""Tests unitarios de `kos_mcp.tools.vector` (Sprint 16/17): storage mockeado."""

from __future__ import annotations

from typing import Any

import pytest

from kos_core.storage import search as search_module
from kos_core.storage.search import SearchHit
from kos_mcp.tools import vector as vector_tools


def _hit(**overrides: Any) -> SearchHit:
    base: dict[str, Any] = {
        "chunk_id": "11111111-1111-1111-1111-111111111111",
        "doc_id": "22222222-2222-2222-2222-222222222222",
        "text": "FastAPI es un framework web",
        "score": 0.9,
        "source": "hybrid",
        "title": "FastAPI",
        "connector": "obsidian",
        "source_id": "fastapi.md",
        "doc_type": "content",
    }
    base.update(overrides)
    return SearchHit(**base)


async def test_search_core_mapea_hits_a_evidencia(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed(texts: list[str]) -> list[list[float]]:
        assert texts == ["fastapi?"]
        return [[0.1, 0.2, 0.3]]

    async def fake_hybrid_search(
        engine: Any, query: str, embedding: Any, **kwargs: Any
    ) -> list[SearchHit]:
        assert query == "fastapi?"
        return [_hit()]

    monkeypatch.setattr(search_module, "hybrid_search", fake_hybrid_search)

    result = await vector_tools._search_core(None, fake_embed, "fastapi?", 10, "hybrid", None)

    assert len(result.evidence) == 1
    assert result.evidence[0].quote == "FastAPI es un framework web"
    assert result.evidence[0].doc_type == "content"
    assert result.degraded is False


async def test_search_core_sin_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.0]]

    async def fake_hybrid_search(
        engine: Any, query: str, embedding: Any, **kwargs: Any
    ) -> list[SearchHit]:
        return []

    monkeypatch.setattr(search_module, "hybrid_search", fake_hybrid_search)

    result = await vector_tools._search_core(None, fake_embed, "nada", 10, "hybrid", None)

    assert result.evidence == []
    assert result.confidence == 0.0


async def test_search_core_modo_lexical_no_embebe(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_embed(texts: list[str]) -> list[list[float]]:
        raise AssertionError("modo lexical no debe embeber la query")

    async def fake_lexical_search(engine: Any, query: str, **kwargs: Any) -> list[SearchHit]:
        return [_hit(source="lexical", score=0.5)]

    monkeypatch.setattr(search_module, "lexical_search", fake_lexical_search)

    result = await vector_tools._search_core(None, fail_embed, "fastapi?", 10, "lexical", None)

    assert len(result.evidence) == 1
    assert result.degraded is False


async def test_search_core_degrada_a_lexical_si_falla_el_embedder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_embed(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("ollama caído")

    async def fake_lexical_search(engine: Any, query: str, **kwargs: Any) -> list[SearchHit]:
        return [_hit(source="lexical", score=0.5)]

    monkeypatch.setattr(search_module, "lexical_search", fake_lexical_search)

    result = await vector_tools._search_core(None, failing_embed, "fastapi?", 10, "hybrid", None)

    assert result.degraded is True
    assert len(result.evidence) == 1
