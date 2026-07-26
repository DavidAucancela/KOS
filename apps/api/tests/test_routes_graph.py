"""Tests de /v1/graph sin Neo4j real (storage mockeado, doc 06 §2, Sprint 9).

La verificación contra Neo4j real (protección de correcciones manuales, APOC,
shortestPath) vive en `packages/core/tests/test_neo4j_integration.py` — acá
solo se prueba el contrato HTTP: status codes, forma de la respuesta, 404/422.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_api.routes import graph as graph_routes
from kos_core.schemas.events import GraphUpdated
from kos_core.storage import neo4j as neo4j_storage

_NOW = datetime.now(UTC)


def _node(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "node-1",
        "node_type": "Technology",
        "canonical_name": "docker",
        "name": "Docker",
        "aliases": [],
        "confidence": 0.8,
        "sources": ["doc-a"],
        "extracted_by": "parser@v1",
        "locked": False,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return base


def _neighbor(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "rel_id": "rel-1",
        "relation_type": "USES",
        "rel_confidence": 0.7,
        "rel_sources": ["doc-a"],
        "rel_extracted_by": "parser@v1",
        "rel_extracted_at": _NOW,
        "rel_rejected": False,
        "neighbor_id": "node-2",
        "neighbor_type": "Project",
        "neighbor_canonical_name": "proyecto-kos",
        "neighbor_name": "Proyecto KOS",
        "neighbor_aliases": [],
        "neighbor_confidence": 0.9,
        "neighbor_sources": ["doc-a"],
        "neighbor_extracted_by": "parser@v1",
        "neighbor_locked": False,
        "direction": "outgoing",
    }
    base.update(overrides)
    return base


def _relation(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "rel-1",
        "relation_type": "USES",
        "source_id": "node-1",
        "target_id": "node-2",
        "confidence": 0.7,
        "sources": ["doc-a"],
        "extracted_by": "parser@v1",
        "extracted_at": _NOW,
        "rejected": False,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _no_real_redis_publish(monkeypatch: pytest.MonkeyPatch) -> list[GraphUpdated]:
    """`publish_event` intentaría una conexión real a Redis; se captura en una
    lista en vez de mockear un cliente completo."""
    published: list[GraphUpdated] = []

    async def fake_publish(client: Any, event: GraphUpdated) -> None:
        published.append(event)

    monkeypatch.setattr(graph_routes, "publish_event", fake_publish)
    return published


def test_get_node_devuelve_nodo_y_vecinos(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_node(driver: Any, node_id: str) -> dict[str, Any]:
        return _node(id=node_id)

    async def fake_get_neighborhood(driver: Any, node_id: str, *, limit: int = 50) -> list[Any]:
        return [_neighbor()]

    monkeypatch.setattr(neo4j_storage, "get_node", fake_get_node)
    monkeypatch.setattr(neo4j_storage, "get_neighborhood", fake_get_neighborhood)

    with TestClient(create_app()) as client:
        response = client.get("/v1/graph/nodes/node-1")

    assert response.status_code == 200
    body = response.json()
    assert body["node"]["id"] == "node-1"
    [neighbor] = body["neighbors"]
    assert neighbor["direction"] == "outgoing"
    assert neighbor["relation"]["source_id"] == "node-1"
    assert neighbor["relation"]["target_id"] == "node-2"
    assert neighbor["node"]["id"] == "node-2"


def test_get_node_404_si_no_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_node(driver: Any, node_id: str) -> None:
        return None

    monkeypatch.setattr(neo4j_storage, "get_node", fake_get_node)
    with TestClient(create_app()) as client:
        response = client.get("/v1/graph/nodes/no-existe")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_get_path_devuelve_nodos_y_relaciones(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_find_path(
        driver: Any, from_id: str, to_id: str, *, max_hops: int = 4
    ) -> tuple[list[Any], list[Any]]:
        return [_node(id=from_id), _node(id=to_id)], [_relation(source_id=from_id, target_id=to_id)]

    monkeypatch.setattr(neo4j_storage, "find_path", fake_find_path)
    with TestClient(create_app()) as client:
        response = client.get("/v1/graph/path", params={"from_id": "node-1", "to_id": "node-2"})

    assert response.status_code == 200
    body = response.json()
    assert [n["id"] for n in body["nodes"]] == ["node-1", "node-2"]
    assert len(body["relations"]) == 1


def test_get_path_404_si_no_hay_camino(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_find_path(driver: Any, from_id: str, to_id: str, *, max_hops: int = 4) -> None:
        return None

    monkeypatch.setattr(neo4j_storage, "find_path", fake_find_path)
    with TestClient(create_app()) as client:
        response = client.get("/v1/graph/path", params={"from_id": "a", "to_id": "b"})

    assert response.status_code == 404


def test_query_nodes_by_type_requiere_node_type() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/graph/query", json={"template": "nodes_by_type"})
    assert response.status_code == 422


def test_query_nodes_by_type(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list(
        driver: Any, node_type: str, *, cursor: str | None, limit: int
    ) -> tuple[list[Any], str | None]:
        return [_node()], "node-1"

    monkeypatch.setattr(neo4j_storage, "list_nodes_by_type", fake_list)
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/graph/query", json={"template": "nodes_by_type", "node_type": "Technology"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["template"] == "nodes_by_type"
    assert len(body["nodes"]) == 1
    assert body["next_cursor"] == "node-1"


def test_query_neighbors_by_type_requiere_node_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/graph/query", json={"template": "neighbors_by_type"})
    assert response.status_code == 422


def test_query_most_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_most_connected(driver: Any, *, node_type: str | None, limit: int) -> list[Any]:
        return [_node()]

    monkeypatch.setattr(neo4j_storage, "most_connected_nodes", fake_most_connected)
    with TestClient(create_app()) as client:
        response = client.post("/v1/graph/query", json={"template": "most_connected"})

    assert response.status_code == 200
    assert response.json()["template"] == "most_connected"


def test_patch_node_corrige_y_publica_evento(
    monkeypatch: pytest.MonkeyPatch, _no_real_redis_publish: list[GraphUpdated]
) -> None:
    async def fake_update_node(
        driver: Any,
        node_id: str,
        *,
        canonical_name: str | None = None,
        node_type: str | None = None,
        aliases: list[str] | None = None,
    ) -> dict[str, Any]:
        return _node(id=node_id, canonical_name=canonical_name or "docker", locked=True)

    monkeypatch.setattr(neo4j_storage, "update_node", fake_update_node)
    with TestClient(create_app()) as client:
        response = client.patch(
            "/v1/graph/nodes/node-1", json={"canonical_name": "docker corrected"}
        )

    assert response.status_code == 200
    assert response.json()["locked"] is True
    assert len(_no_real_redis_publish) == 1
    assert _no_real_redis_publish[0].node_ids == ["node-1"]


def test_patch_node_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_update_node(driver: Any, node_id: str, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(neo4j_storage, "update_node", fake_update_node)
    with TestClient(create_app()) as client:
        response = client.patch("/v1/graph/nodes/no-existe", json={})

    assert response.status_code == 404


def test_patch_node_tipo_invalido_es_422(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_update_node(driver: Any, node_id: str, **kwargs: Any) -> None:
        raise ValueError("Tipo de nodo desconocido: 'Robot'")

    monkeypatch.setattr(neo4j_storage, "update_node", fake_update_node)
    with TestClient(create_app()) as client:
        response = client.patch("/v1/graph/nodes/node-1", json={"node_type": "Robot"})

    assert response.status_code == 422


def test_patch_relation_corrige_y_publica_evento(
    monkeypatch: pytest.MonkeyPatch, _no_real_redis_publish: list[GraphUpdated]
) -> None:
    async def fake_update_relation(
        driver: Any,
        relation_id: str,
        *,
        relation_type: str | None = None,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        return _relation(id=relation_id, relation_type=relation_type or "USES")

    monkeypatch.setattr(neo4j_storage, "update_relation", fake_update_relation)
    with TestClient(create_app()) as client:
        response = client.patch("/v1/graph/relations/rel-1", json={"relation_type": "RELATED_TO"})

    assert response.status_code == 200
    assert response.json()["relation_type"] == "RELATED_TO"
    assert _no_real_redis_publish[0].relation_ids == ["rel-1"]


def test_delete_relation_rechaza(
    monkeypatch: pytest.MonkeyPatch, _no_real_redis_publish: list[GraphUpdated]
) -> None:
    async def fake_reject(driver: Any, relation_id: str) -> bool:
        return True

    monkeypatch.setattr(neo4j_storage, "reject_relation", fake_reject)
    with TestClient(create_app()) as client:
        response = client.delete("/v1/graph/relations/rel-1")

    assert response.status_code == 204
    assert _no_real_redis_publish[0].relation_ids == ["rel-1"]


def test_delete_relation_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_reject(driver: Any, relation_id: str) -> bool:
        return False

    monkeypatch.setattr(neo4j_storage, "reject_relation", fake_reject)
    with TestClient(create_app()) as client:
        response = client.delete("/v1/graph/relations/no-existe")

    assert response.status_code == 404
