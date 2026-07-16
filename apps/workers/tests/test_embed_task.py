import uuid
from collections.abc import Sequence

import pytest

from kos_workers.celery_app import app
from kos_workers.tasks import embed as embed_module


async def test_embed_in_batches_preserva_orden_y_lotea() -> None:
    calls: list[list[str]] = []

    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        calls.append(list(texts))
        return [[float(len(text))] for text in texts]

    texts = [f"texto-{i}" * (i + 1) for i in range(7)]
    vectors = await embed_module._embed_in_batches(texts, fake_embed, batch_size=3)

    assert [len(batch) for batch in calls] == [3, 3, 1]
    assert vectors == [[float(len(text))] for text in texts]


async def test_embed_in_batches_sin_textos_no_llama() -> None:
    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        raise AssertionError("no debe llamarse")

    assert await embed_module._embed_in_batches([], fake_embed) == []


def test_task_eager_devuelve_contadores_y_encadena_enrich(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc_id = str(uuid.uuid4())
    enriched: list[str] = []

    async def fake_embed_document(value: uuid.UUID) -> int:
        assert str(value) == doc_id
        return 4

    class _StubEnrich:
        def delay(self, value: str) -> None:
            enriched.append(value)

    monkeypatch.setattr(embed_module, "_embed_document", fake_embed_document)
    monkeypatch.setattr(embed_module, "enrich_document", _StubEnrich())
    app.conf.task_always_eager = True
    try:
        result = embed_module.embed_document.delay(doc_id).get()
    finally:
        app.conf.task_always_eager = False

    assert result == {"doc_id": doc_id, "embedded": 4}
    assert enriched == [doc_id]  # el enriquecido queda encolado tras embeber


def test_la_task_esta_registrada_con_nombre_de_evento() -> None:
    assert "kos.embed_document" in app.tasks
