"""Tests unitarios de `kos_mcp.tools.recommendations` (Sprint 22, doc 11 §5/§6):
storage mockeado."""

from __future__ import annotations

from typing import Any

import pytest

from kos_core.storage import postgres as postgres_module
from kos_mcp.tools import recommendations as recommendations_tools


async def test_store_core_sin_confirm_no_escribe(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_insert(engine: Any, **kwargs: Any) -> None:
        raise AssertionError("no debe escribir sin confirm=True")

    monkeypatch.setattr(postgres_module, "insert_recommendation", fail_insert)

    result = await recommendations_tools._store_core(
        None,
        type="gap",
        title="Título",
        description="",
        evidence=[],
        target_entities=[],
        confidence=0.0,
        priority=0,
        source_event_id=None,
        confirm=False,
        trace_id="trace-1",
    )

    assert result.approved is False
    assert result.recommendation_id is None
    assert "confirm=true" in result.message


async def test_store_core_con_confirm_escribe(monkeypatch: pytest.MonkeyPatch) -> None:
    inserted: list[dict[str, Any]] = []

    async def fake_insert(engine: Any, **kwargs: Any) -> None:
        inserted.append(kwargs)

    monkeypatch.setattr(postgres_module, "insert_recommendation", fake_insert)

    result = await recommendations_tools._store_core(
        None,
        type="gap",
        title="Docker es prerrequisito de Kubernetes",
        description="Falta KNOWS entre el usuario y Docker",
        evidence=[{"node_id": "node-1"}],
        target_entities=["node-1", "node-2"],
        confidence=0.6,
        priority=1,
        source_event_id="trace-source",
        confirm=True,
        trace_id="trace-1",
    )

    assert result.approved is True
    assert result.recommendation_id is not None
    [call] = inserted
    assert call["type"] == "gap"
    assert call["title"] == "Docker es prerrequisito de Kubernetes"
    assert call["target_entities"] == ["node-1", "node-2"]
    assert call["status"] == "pending"
    assert call["source_event_id"] == "trace-source"
