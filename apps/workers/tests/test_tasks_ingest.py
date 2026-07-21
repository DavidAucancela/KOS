"""Sprint 7: `kos.sync_all_sources` (polling programado, doc 05 §2)."""

import uuid

import pytest

from kos_workers.celery_app import app
from kos_workers.tasks import ingest as ingest_module


async def test_enabled_source_uuids_filtra_deshabilitadas(monkeypatch: pytest.MonkeyPatch) -> None:
    enabled_id = uuid.uuid4()

    class _FakeRow:
        def __init__(self, source_uuid: uuid.UUID) -> None:
            self.source_uuid = source_uuid

    class _FakeResult:
        def __iter__(self) -> object:
            return iter([_FakeRow(enabled_id)])

    class _FakeConn:
        async def execute(self, query: object) -> _FakeResult:
            return _FakeResult()

        async def __aenter__(self) -> "_FakeConn":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    class _FakeEngine:
        def connect(self) -> _FakeConn:
            return _FakeConn()

        async def dispose(self) -> None:
            return None

    monkeypatch.setattr(ingest_module, "create_engine", lambda settings: _FakeEngine())

    result = await ingest_module._enabled_source_uuids(ingest_module.get_settings())
    assert result == [enabled_id]


def test_sync_all_sources_encola_por_cada_fuente_habilitada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = [uuid.uuid4(), uuid.uuid4()]

    async def fake_enabled(settings: object) -> list[uuid.UUID]:
        return ids

    encoladas: list[str] = []

    class _FakeDelay:
        def delay(self, source_uuid: str) -> None:
            encoladas.append(source_uuid)

    monkeypatch.setattr(ingest_module, "_enabled_source_uuids", fake_enabled)
    monkeypatch.setattr(ingest_module, "sync_source", _FakeDelay())

    result = ingest_module.sync_all_sources()

    assert result == {"sources": 2}
    assert encoladas == [str(i) for i in ids]


def test_la_task_esta_registrada_con_nombre_de_evento() -> None:
    assert "kos.sync_all_sources" in app.tasks
