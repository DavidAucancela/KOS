import uuid

import pytest

from kos_workers.celery_app import app
from kos_workers.tasks import enrich as enrich_module
from kos_workers.tasks.enrich import _Loaded


async def _fake_generate(prompt: str) -> str:
    return "  Resumen fiel del documento.  "


async def test_enrich_persiste_resumen_y_keywords(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_id = uuid.uuid4()
    persisted: dict[str, object] = {}

    async def fake_load(engine: object, value: uuid.UUID) -> _Loaded:
        assert value == doc_id
        return ("Docker", None, ["infra"], "docker docker contenedores")

    async def fake_persist(
        engine: object, value: uuid.UUID, *, summary: str | None, keywords: list[str]
    ) -> None:
        persisted["summary"] = summary
        persisted["keywords"] = keywords

    monkeypatch.setattr(enrich_module, "_load_document", fake_load)
    monkeypatch.setattr(enrich_module, "_persist_enrichment", fake_persist)

    result = await enrich_module._enrich(doc_id, generate=_fake_generate, engine=None)

    keywords = persisted["keywords"]
    assert isinstance(keywords, list)
    assert result == {"doc_id": str(doc_id), "enriched": True, "keywords": len(keywords)}
    assert persisted["summary"] == "Resumen fiel del documento."
    assert "infra" in keywords
    assert "docker" in keywords


async def test_enrich_idempotente_si_ya_tiene_resumen(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_id = uuid.uuid4()

    async def fake_load(engine: object, value: uuid.UUID) -> _Loaded:
        return ("t", "ya tiene resumen", ["infra"], "texto")

    async def fail_persist(*args: object, **kwargs: object) -> None:
        raise AssertionError("no debe persistir un documento ya enriquecido")

    monkeypatch.setattr(enrich_module, "_load_document", fake_load)
    monkeypatch.setattr(enrich_module, "_persist_enrichment", fail_persist)

    result = await enrich_module._enrich(doc_id, generate=_fake_generate, engine=None)
    assert result == {"doc_id": str(doc_id), "enriched": False}


async def test_enrich_documento_inexistente(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_id = uuid.uuid4()

    async def fake_load(engine: object, value: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(enrich_module, "_load_document", fake_load)
    result = await enrich_module._enrich(doc_id, generate=_fake_generate, engine=None)
    assert result == {"doc_id": str(doc_id), "enriched": False}


def test_la_task_esta_registrada_con_nombre_de_evento() -> None:
    assert "kos.enrich_document" in app.tasks
