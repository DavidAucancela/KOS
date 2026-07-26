"""Tests de la rama s0 "no fabricar plantillas" (Sprint 8), sin infraestructura real."""

import uuid
from collections.abc import Sequence
from typing import Any

import pytest

from kos_api.services import notes_service, template_intent_service
from kos_core.storage import search as search_storage
from kos_core.storage.search import RRF_K, SearchHit

_MAX_HYBRID_SCORE = 2.0 / (RRF_K + 1)


def _template_hit(**overrides: Any) -> SearchHit:
    base: dict[str, Any] = {
        "chunk_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "text": "Plantilla: Proyecto — README de un proyecto.",
        "score": _MAX_HYBRID_SCORE * 0.9,
        "source": "hybrid",
        "title": "<% tp.file.title %>",
        "connector": "obsidian",
        "source_id": "_Templates/Proyecto.md",
        "doc_type": "template",
    }
    base.update(overrides)
    return SearchHit(**base)


class _FakeEmbedder:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]

    async def aclose(self) -> None:
        return None


async def test_candidata_clara_no_pasa_por_llm_y_cita_la_plantilla_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hit = _template_hit()

    async def fake_hybrid(*args: Any, **kwargs: Any) -> list[SearchHit]:
        assert kwargs["doc_type"] == "template"
        return [hit]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)

    result = await template_intent_service.resolve_template_intent(
        engine=None,  # type: ignore[arg-type]
        embedder=_FakeEmbedder(),
        query="quiero crear información para describir un proyecto, ¿qué plantilla me sirve?",
        trace_id="t1",
    )

    assert result.confidence == 1.0
    assert result.plan == [
        template_intent_service.PlanStep(
            id="s0", agent="intent", task="detectar intención de creación de nota"
        )
    ]
    [ev] = result.evidence
    assert ev.source_id == "_Templates/Proyecto.md"
    assert "Proyecto" in result.answer
    assert "/crear-nota Proyecto" in result.answer


async def test_sin_candidatas_lista_las_plantillas_existentes_y_pregunta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_hybrid(*args: Any, **kwargs: Any) -> list[SearchHit]:
        return []

    async def fake_list_templates(engine: Any) -> list[notes_service.TemplateInfo]:
        return [
            notes_service.TemplateInfo(
                template_name="Proyecto", title="Proyecto", source_id="_Templates/Proyecto.md"
            ),
            notes_service.TemplateInfo(
                template_name="MaquinaHTB", title="MaquinaHTB", source_id="_Templates/MaquinaHTB.md"
            ),
        ]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(notes_service, "list_templates", fake_list_templates)

    result = await template_intent_service.resolve_template_intent(
        engine=None,  # type: ignore[arg-type]
        embedder=_FakeEmbedder(),
        query="quiero crear información para describir un proyecto",
        trace_id="t2",
    )

    assert result.confidence == 0.0
    assert result.evidence == []
    assert "Proyecto" in result.answer
    assert "MaquinaHTB" in result.answer
    assert "¿Para qué" in result.answer


async def test_candidatas_empatadas_es_ambiguo(monkeypatch: pytest.MonkeyPatch) -> None:
    top = _template_hit(source_id="_Templates/Proyecto.md", score=_MAX_HYBRID_SCORE * 0.9)
    second = _template_hit(source_id="_Templates/Reunion.md", score=_MAX_HYBRID_SCORE * 0.85)

    async def fake_hybrid(*args: Any, **kwargs: Any) -> list[SearchHit]:
        return [top, second]

    async def fake_list_templates(engine: Any) -> list[notes_service.TemplateInfo]:
        return []

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(notes_service, "list_templates", fake_list_templates)

    result = await template_intent_service.resolve_template_intent(
        engine=None,  # type: ignore[arg-type]
        embedder=_FakeEmbedder(),
        query="qué plantilla uso",
        trace_id="t3",
    )

    assert result.confidence == 0.0
    assert result.evidence == []
