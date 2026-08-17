import uuid

import pytest

from kos_core.schemas import EntityCandidate
from kos_core.storage import neo4j as neo4j_module
from kos_workers.celery_app import app
from kos_workers.tasks import graph_sync as graph_sync_module


def _entity(name: str, type_: str = "Technology", confidence: float = 0.8) -> EntityCandidate:
    return EntityCandidate(name=name, type=type_, confidence=confidence)


async def _no_candidates(driver: object, node_type: str) -> list[neo4j_module.NodeRecord]:
    return []


async def _no_merge_verdict(name_a: str, name_b: str) -> bool:
    raise AssertionError("no debe pedirse veredicto sin candidatos similares")


class _RecordingMerge:
    """Fake de `merge_node`: registra las llamadas y devuelve un id determinista."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def __call__(self, driver: object, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return f"node-{len(self.calls)}"


async def test_resolve_entity_crea_nodo_nuevo_sin_candidatos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(neo4j_module, "fetch_nodes_by_type", _no_candidates)
    recording = _RecordingMerge()
    monkeypatch.setattr(neo4j_module, "merge_node", recording)

    async def embed(texts: list[str]) -> list[list[float]]:
        raise AssertionError("sin candidatos no debe embeberse nada")

    node_id = await graph_sync_module._resolve_entity(
        None, _entity("FastAPI"), doc_id="doc-1", embed=embed, merge_verdict=_no_merge_verdict
    )

    assert node_id == "node-1"
    assert recording.calls[0]["canonical_name"] == "fastapi"
    assert recording.calls[0]["sources"] == ["doc-1"]
    assert recording.calls[0]["source_confidences"] == [0.8]  # doc 04 §5


async def test_resolve_entity_match_exacto_fusiona(monkeypatch: pytest.MonkeyPatch) -> None:
    async def existing(driver: object, node_type: str) -> list[neo4j_module.NodeRecord]:
        return [
            neo4j_module.NodeRecord(
                {
                    "id": "node-existente",
                    "canonical_name": "fastapi",
                    "name": "FastAPI",
                    "aliases": ["fast-api"],
                    "confidence": 0.6,
                    "sources": ["doc-viejo"],
                }
            )
        ]

    monkeypatch.setattr(neo4j_module, "fetch_nodes_by_type", existing)
    recording = _RecordingMerge()
    monkeypatch.setattr(neo4j_module, "merge_node", recording)

    async def embed(texts: list[str]) -> list[list[float]]:
        raise AssertionError("match exacto no debe pasar a embeddings")

    await graph_sync_module._resolve_entity(
        None,
        _entity("FastAPI", confidence=0.9),
        doc_id="doc-nuevo",
        embed=embed,
        merge_verdict=_no_merge_verdict,
    )

    call = recording.calls[0]
    assert set(call["sources"]) == {"doc-viejo", "doc-nuevo"}  # type: ignore[arg-type]
    assert call["confidence"] == pytest.approx(0.95)  # max(0.6, 0.9) + 0.05
    # doc 04 §5: "doc-viejo" no tenía source_confidences propio (dato previo a
    # este sprint) → usa la confidence agregada (0.6) como mejor aproximación;
    # "doc-nuevo" guarda la confidence cruda de esta extracción (0.9).
    sources = call["sources"]
    confidences = call["source_confidences"]
    assert dict(zip(sources, confidences, strict=True)) == {  # type: ignore[arg-type]
        "doc-viejo": 0.6,
        "doc-nuevo": 0.9,
    }


async def test_resolve_entity_similitud_alta_pide_veredicto_y_fusiona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def existing(driver: object, node_type: str) -> list[neo4j_module.NodeRecord]:
        return [
            neo4j_module.NodeRecord(
                {
                    "id": "node-existente",
                    "canonical_name": "fastapi-framework",
                    "name": "Fast API Framework",
                    "aliases": [],
                    "confidence": 0.5,
                    "sources": ["doc-viejo"],
                }
            )
        ]

    monkeypatch.setattr(neo4j_module, "fetch_nodes_by_type", existing)
    recording = _RecordingMerge()
    monkeypatch.setattr(neo4j_module, "merge_node", recording)

    async def embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0], [0.99, 0.01]]  # muy similares, coseno > 0.9

    verdicts: list[tuple[str, str]] = []

    async def merge_verdict(name_a: str, name_b: str) -> bool:
        verdicts.append((name_a, name_b))
        return True

    node_id = await graph_sync_module._resolve_entity(
        None, _entity("FastAPI"), doc_id="doc-nuevo", embed=embed, merge_verdict=merge_verdict
    )

    assert node_id == "node-1"
    assert verdicts == [("FastAPI", "Fast API Framework")]
    assert recording.calls[0]["canonical_name"] == "fastapi-framework"


async def test_resolve_entity_veredicto_negativo_crea_nodo_nuevo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def existing(driver: object, node_type: str) -> list[neo4j_module.NodeRecord]:
        return [
            neo4j_module.NodeRecord(
                {
                    "id": "otro",
                    "canonical_name": "otraentidad",
                    "name": "Otra Entidad",
                    "aliases": [],
                    "confidence": 0.5,
                    "sources": ["doc-x"],
                }
            )
        ]

    monkeypatch.setattr(neo4j_module, "fetch_nodes_by_type", existing)
    recording = _RecordingMerge()
    monkeypatch.setattr(neo4j_module, "merge_node", recording)

    async def embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0], [0.99, 0.01]]

    async def merge_verdict(name_a: str, name_b: str) -> bool:
        return False

    await graph_sync_module._resolve_entity(
        None, _entity("FastAPI"), doc_id="doc-nuevo", embed=embed, merge_verdict=merge_verdict
    )

    assert recording.calls[0]["canonical_name"] == "fastapi"  # nodo nuevo, no fusionado


async def test_sync_graph_documento_inexistente(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_id = uuid.uuid4()

    async def fake_load(engine: object, value: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(graph_sync_module, "_load_document_text", fake_load)

    async def unreachable(*args: object, **kwargs: object) -> str:
        raise AssertionError("no debe llamarse")

    result = await graph_sync_module._sync_graph(
        doc_id,
        engine=None,
        driver=None,
        generate_entities=unreachable,
        generate_relations=unreachable,
        embed=unreachable,
        merge_verdict=unreachable,
    )
    assert result == {"doc_id": str(doc_id), "synced": False}


async def test_sync_graph_extrae_resuelve_y_conecta(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_id = uuid.uuid4()

    async def fake_load(engine: object, value: uuid.UUID) -> tuple[str, str]:
        return "Proyecto KOS", "KOS usa FastAPI."

    monkeypatch.setattr(graph_sync_module, "_load_document_text", fake_load)
    monkeypatch.setattr(neo4j_module, "fetch_nodes_by_type", _no_candidates)
    recording_nodes = _RecordingMerge()
    monkeypatch.setattr(neo4j_module, "merge_node", recording_nodes)

    relations_written: list[dict[str, object]] = []

    async def fake_merge_relation(driver: object, **kwargs: object) -> None:
        relations_written.append(kwargs)

    monkeypatch.setattr(neo4j_module, "merge_relation", fake_merge_relation)

    entities_json = (
        '[{"name": "Proyecto KOS", "type": "Project", "confidence": 0.9}, '
        '{"name": "FastAPI", "type": "Technology", "confidence": 0.9}]'
    )
    relations_json = (
        '[{"source": "Proyecto KOS", "relation": "USES", "target": "FastAPI", "confidence": 0.9}]'
    )

    async def generate_entities(prompt: str) -> str:
        return entities_json

    async def generate_relations(prompt: str) -> str:
        return relations_json

    async def embed(texts: list[str]) -> list[list[float]]:
        raise AssertionError("sin candidatos existentes no debe embeberse")

    result = await graph_sync_module._sync_graph(
        doc_id,
        engine=None,
        driver=None,
        generate_entities=generate_entities,
        generate_relations=generate_relations,
        embed=embed,
        merge_verdict=_no_merge_verdict,
    )

    assert result["synced"] is True
    assert result["entities"] == 2
    assert result["relations"] == 1
    assert len(relations_written) == 1
    assert relations_written[0]["relation_type"] == "USES"
    assert sorted(result["node_ids"]) == ["node-1", "node-2"]


def test_la_task_esta_registrada_con_nombre_de_evento() -> None:
    assert "kos.graph_sync" in app.tasks


def test_graph_sync_task_encadena_recomendador_si_sincronizo_algo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprint 22, doc 11 §3.1: hasta este sprint, `kos.graph_sync` nunca
    disparaba `graph.updated` pese a que su propio evento decía que sí — acá
    se prueba que la task encadena `kos.recommend_from_graph_update` cuando
    sincronizó nodos reales."""

    async def fake_async_graph_sync(doc_id: uuid.UUID) -> dict[str, object]:
        return {"doc_id": str(doc_id), "synced": True, "node_ids": ["node-1", "node-2"]}

    monkeypatch.setattr(graph_sync_module, "_async_graph_sync", fake_async_graph_sync)

    from kos_workers.tasks import recommend as recommend_module

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        recommend_module.recommend_from_graph_update,
        "delay",
        lambda **kwargs: calls.append(kwargs),
    )

    result = graph_sync_module.graph_sync(str(uuid.uuid4()))

    assert result["synced"] is True
    [call] = calls
    assert sorted(call["node_ids"]) == ["node-1", "node-2"]
    assert call["relation_ids"] == []


def test_graph_sync_task_no_encadena_si_no_sincronizo(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_async_graph_sync(doc_id: uuid.UUID) -> dict[str, object]:
        return {"doc_id": str(doc_id), "synced": False}

    monkeypatch.setattr(graph_sync_module, "_async_graph_sync", fake_async_graph_sync)

    from kos_workers.tasks import recommend as recommend_module

    def fail_delay(**kwargs: object) -> None:
        raise AssertionError("no debe encadenar el Recomendador si no sincronizó nada")

    monkeypatch.setattr(recommend_module.recommend_from_graph_update, "delay", fail_delay)

    result = graph_sync_module.graph_sync(str(uuid.uuid4()))

    assert result["synced"] is False
