"""Tests de las tasks del Recomendador (Sprint 22 debounce, Sprint 23 lagunas
de conocimiento, Sprint 24 contradicciones, doc 11 §3/§4): Redis y MCP
mockeados, sin infra real — mismo estilo que `test_memory_task.py`."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from kos_agents.recommender import RecommenderAgent
from kos_core.storage import postgres as postgres_module
from kos_core.storage import redis as redis_module
from kos_core.storage import search as search_module
from kos_core.storage.search import SearchHit
from kos_workers.celery_app import app
from kos_workers.tasks import recommend as recommend_module


class _FakeSyncRedis:
    """Sustituto mínimo de `redis.Redis` síncrono: sets + string, sin TTL ni
    persistencia real (alcanza para probar el debounce de un solo proceso)."""

    def __init__(self) -> None:
        self._sets: dict[str, set[str]] = {}
        self._strings: dict[str, str] = {}
        self.closed = False

    def sadd(self, key: str, *values: str) -> None:
        self._sets.setdefault(key, set()).update(values)

    def smembers(self, key: str) -> set[str]:
        return set(self._sets.get(key, set()))

    def set(self, key: str, value: str) -> None:
        self._strings[key] = value

    def get(self, key: str) -> str | None:
        return self._strings.get(key)

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._sets.pop(key, None)
            self._strings.pop(key, None)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeSyncRedis:
    client = _FakeSyncRedis()
    monkeypatch.setattr(redis_module, "create_sync_client", lambda settings: client)
    return client


def test_recommend_from_graph_update_acumula_y_programa_flush(
    monkeypatch: pytest.MonkeyPatch, fake_redis: _FakeSyncRedis
) -> None:
    scheduled: list[dict[str, Any]] = []

    def fake_apply_async(*, kwargs: dict[str, Any], countdown: float) -> None:
        scheduled.append({"kwargs": kwargs, "countdown": countdown})

    monkeypatch.setattr(recommend_module.recommend_flush, "apply_async", fake_apply_async)

    result = recommend_module.recommend_from_graph_update(
        node_ids=["node-1"], relation_ids=[], trace_id="trace-1"
    )

    assert result["scheduled"] is True
    assert fake_redis.smembers(recommend_module._PENDING_NODES_KEY) == {"node-1"}
    [scheduled_call] = scheduled
    assert scheduled_call["countdown"] == recommend_module.DEBOUNCE_SECONDS
    assert scheduled_call["kwargs"]["token"] == result["token"]
    assert scheduled_call["kwargs"]["trace_id"] == "trace-1"


def test_recommend_from_graph_update_dos_disparos_agrupan_en_un_solo_token(
    monkeypatch: pytest.MonkeyPatch, fake_redis: _FakeSyncRedis
) -> None:
    """Doc 11 §3.2: una resincronización que toca varios documentos no debe
    disparar una pasada del Recomendador por cada uno — el segundo disparo
    reemplaza el token del primero (el flush viejo queda superado)."""
    monkeypatch.setattr(recommend_module.recommend_flush, "apply_async", lambda **kwargs: None)

    first = recommend_module.recommend_from_graph_update(
        node_ids=["node-1"], relation_ids=[], trace_id=None
    )
    second = recommend_module.recommend_from_graph_update(
        node_ids=["node-2"], relation_ids=["rel-1"], trace_id=None
    )

    assert first["token"] != second["token"]
    assert fake_redis.smembers(recommend_module._PENDING_NODES_KEY) == {"node-1", "node-2"}
    assert fake_redis.smembers(recommend_module._PENDING_RELATIONS_KEY) == {"rel-1"}
    assert fake_redis.get(recommend_module._FLUSH_TOKEN_KEY) == second["token"]


def test_recommend_flush_token_superado_es_no_op(
    monkeypatch: pytest.MonkeyPatch, fake_redis: _FakeSyncRedis
) -> None:
    fake_redis.set(recommend_module._FLUSH_TOKEN_KEY, "token-nuevo")
    fake_redis.sadd(recommend_module._PENDING_NODES_KEY, "node-1")

    async def fail_recommend(**kwargs: Any) -> dict[str, Any]:
        raise AssertionError("un flush superado no debe invocar al RecommenderAgent")

    monkeypatch.setattr(recommend_module, "_async_recommend", fail_recommend)

    result = recommend_module.recommend_flush(token="token-viejo")

    assert result == {"superseded": True, "recommendation_id": None}
    # El flush superado no debe limpiar el estado que dejó el disparo más nuevo.
    assert fake_redis.get(recommend_module._FLUSH_TOKEN_KEY) == "token-nuevo"


def test_recommend_flush_sin_pendientes_es_no_op(
    monkeypatch: pytest.MonkeyPatch, fake_redis: _FakeSyncRedis
) -> None:
    fake_redis.set(recommend_module._FLUSH_TOKEN_KEY, "token-1")

    async def fail_recommend(**kwargs: Any) -> dict[str, Any]:
        raise AssertionError("sin node_ids/relation_ids no debe invocar al RecommenderAgent")

    monkeypatch.setattr(recommend_module, "_async_recommend", fail_recommend)

    result = recommend_module.recommend_flush(token="token-1")

    assert result == {"superseded": False, "recommendation_id": None}


def test_recommend_flush_token_vigente_invoca_al_recomendador(
    monkeypatch: pytest.MonkeyPatch, fake_redis: _FakeSyncRedis
) -> None:
    fake_redis.set(recommend_module._FLUSH_TOKEN_KEY, "token-1")
    fake_redis.sadd(recommend_module._PENDING_NODES_KEY, "node-1", "node-2")

    calls: list[dict[str, Any]] = []

    async def fake_recommend(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"recommendation_id": "rec-1"}

    monkeypatch.setattr(recommend_module, "_async_recommend", fake_recommend)

    result = recommend_module.recommend_flush(token="token-1", trace_id="trace-1")

    assert result == {"superseded": False, "recommendation_id": "rec-1"}
    [call] = calls
    assert sorted(call["node_ids"]) == ["node-1", "node-2"]
    assert call["trace_id"] == "trace-1"
    # El estado pendiente se limpia tras un flush real, no solo tras uno superado.
    assert fake_redis.smembers(recommend_module._PENDING_NODES_KEY) == set()
    assert fake_redis.get(recommend_module._FLUSH_TOKEN_KEY) is None


class _FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] for _ in texts]

    async def aclose(self) -> None:
        return None


class _FakeLLM:
    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        return '{"contradicts": false, "explanation": ""}'

    async def aclose(self) -> None:
        return None


class _FakeDriver:
    async def close(self) -> None:
        return None


class _FakeEngine:
    async def dispose(self) -> None:
        return None


def _gap_candidate(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "node_id": "node-1",
        "canonical_name": "docker",
        "name": "Docker",
        "confidence": 0.3,
        "blocks": ["Kubernetes"],
    }
    base.update(overrides)
    return base


def _no_op_result(**overrides: Any) -> dict[str, Any]:
    """Forma completa del resultado de `_async_recommend` (gaps + contradicciones,
    Sprint 23/24) con ambos sub-resultados en cero por defecto."""
    base: dict[str, Any] = {
        "candidates_found": 0,
        "recommendations_created": 0,
        "contradiction_candidates_checked": 0,
        "contradiction_recommendations_created": 0,
    }
    base.update(overrides)
    return base


def _patch_infra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recommend_module, "create_engine", lambda settings: _FakeEngine())
    monkeypatch.setattr(
        recommend_module.neo4j_storage, "create_driver", lambda settings: _FakeDriver()
    )
    monkeypatch.setattr(recommend_module, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    monkeypatch.setattr(recommend_module, "OllamaLLMClient", lambda settings: _FakeLLM())

    async def fake_recent_seed_chunks(engine: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(postgres_module, "recent_seed_chunks", fake_recent_seed_chunks)


async def test_async_recommend_crea_una_recomendacion_por_candidato_nuevo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_async_recommend` (Sprint 23, doc 11 §4/§5) consulta
    `gaps_by_prerequisite` y persiste una `Recommendation(type="gap")` real por
    candidato nuevo, vía el `RecommenderAgent` real sobre MCP embebido (mismo
    patrón que `kos.memory_learn`, Sprint 21) — probado acá con
    `insert_recommendation` mockeado, sin Postgres/Neo4j/Ollama reales."""
    inserted: list[dict[str, Any]] = []

    async def fake_insert(engine: Any, **kwargs: Any) -> None:
        inserted.append(kwargs)

    async def fake_gaps(driver: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [_gap_candidate()]

    async def fake_has_pending(engine: Any, **kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(postgres_module, "insert_recommendation", fake_insert)
    monkeypatch.setattr(postgres_module, "has_pending_recommendation", fake_has_pending)
    monkeypatch.setattr(recommend_module.neo4j_storage, "gaps_by_prerequisite", fake_gaps)
    _patch_infra(monkeypatch)

    result = await recommend_module._async_recommend(
        node_ids=["node-1"], relation_ids=[], trace_id="trace-1"
    )

    assert result == _no_op_result(candidates_found=1, recommendations_created=1)
    [call] = inserted
    assert call["type"] == "gap"
    assert call["target_entities"] == ["node-1"]
    assert call["source_event_id"] == "trace-1"
    assert call["confidence"] == pytest.approx(0.7)  # 1.0 - 0.3
    assert call["priority"] == 1  # len(blocks)
    assert "Docker" in call["title"]


async def test_async_recommend_salta_candidatos_ya_pendientes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_insert(engine: Any, **kwargs: Any) -> None:
        raise AssertionError("no debe reinsertar una laguna ya pendiente")

    async def fake_gaps(driver: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [_gap_candidate()]

    async def fake_has_pending(engine: Any, **kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(postgres_module, "insert_recommendation", fail_insert)
    monkeypatch.setattr(postgres_module, "has_pending_recommendation", fake_has_pending)
    monkeypatch.setattr(recommend_module.neo4j_storage, "gaps_by_prerequisite", fake_gaps)
    _patch_infra(monkeypatch)

    result = await recommend_module._async_recommend(
        node_ids=[], relation_ids=[], trace_id="trace-1"
    )

    assert result == _no_op_result(candidates_found=1)


async def test_async_recommend_respeta_el_tope_por_pasada(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = [_gap_candidate(node_id=f"node-{i}", name=f"Concepto {i}") for i in range(10)]
    inserted: list[dict[str, Any]] = []

    async def fake_insert(engine: Any, **kwargs: Any) -> None:
        inserted.append(kwargs)

    async def fake_gaps(driver: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return candidates

    async def fake_has_pending(engine: Any, **kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(postgres_module, "insert_recommendation", fake_insert)
    monkeypatch.setattr(postgres_module, "has_pending_recommendation", fake_has_pending)
    monkeypatch.setattr(recommend_module.neo4j_storage, "gaps_by_prerequisite", fake_gaps)
    _patch_infra(monkeypatch)

    result = await recommend_module._async_recommend(
        node_ids=[], relation_ids=[], trace_id="trace-1"
    )

    assert result == _no_op_result(
        candidates_found=10,
        recommendations_created=recommend_module.MAX_GAP_RECOMMENDATIONS_PER_RUN,
    )
    assert len(inserted) == recommend_module.MAX_GAP_RECOMMENDATIONS_PER_RUN


async def test_async_recommend_sin_candidatos_no_crea_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_insert(engine: Any, **kwargs: Any) -> None:
        raise AssertionError("sin candidatos no debe invocar al RecommenderAgent")

    async def fake_gaps(driver: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(postgres_module, "insert_recommendation", fail_insert)
    monkeypatch.setattr(recommend_module.neo4j_storage, "gaps_by_prerequisite", fake_gaps)
    _patch_infra(monkeypatch)

    result = await recommend_module._async_recommend(
        node_ids=[], relation_ids=[], trace_id="trace-1"
    )

    assert result == _no_op_result()


def _seed_chunk(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "chunk_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "text": "Redis es un almacén clave-valor en memoria.",
        "embedding": [0.1, 0.2, 0.3],
        "title": "Nota A",
    }
    base.update(overrides)
    return base


def _match_hit(**overrides: Any) -> SearchHit:
    base: dict[str, Any] = {
        "chunk_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "text": "Redis persiste todo a disco por defecto.",
        "score": 0.85,
        "source": "vector",
        "title": "Nota B",
    }
    base.update(overrides)
    return SearchHit.model_validate(base)


async def test_default_contradiction_verdict_json_valido_true() -> None:
    async def generate(prompt: str, *, system: str) -> str:
        return '{"contradicts": true, "explanation": "A dice X, B dice lo opuesto"}'

    contradicts, explanation = await recommend_module._default_contradiction_verdict(
        generate, "texto A", "texto B"
    )

    assert contradicts is True
    assert explanation == "A dice X, B dice lo opuesto"


async def test_default_contradiction_verdict_json_valido_false() -> None:
    async def generate(prompt: str, *, system: str) -> str:
        return '{"contradicts": false, "explanation": ""}'

    contradicts, explanation = await recommend_module._default_contradiction_verdict(
        generate, "texto A", "texto B"
    )

    assert contradicts is False
    assert explanation == ""


async def test_default_contradiction_verdict_json_invalido_falla_a_false() -> None:
    async def generate(prompt: str, *, system: str) -> str:
        return "no es json"

    contradicts, explanation = await recommend_module._default_contradiction_verdict(
        generate, "texto A", "texto B"
    )

    assert contradicts is False
    assert explanation == ""


async def test_async_recommend_contradiccion_confirmada_crea_recomendacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted: list[dict[str, Any]] = []

    async def fake_insert(engine: Any, **kwargs: Any) -> None:
        inserted.append(kwargs)

    async def fake_gaps(driver: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    seed = _seed_chunk()
    match = _match_hit()

    async def fake_seed_chunks(engine: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [seed]

    async def fake_band(engine: Any, embedding: Any, **kwargs: Any) -> list[SearchHit]:
        return [match]

    async def fake_has_pending(engine: Any, **kwargs: Any) -> bool:
        return False

    class _ConfirmingLLM:
        async def generate(self, prompt: str, *, system: str | None = None) -> str:
            return '{"contradicts": true, "explanation": "se contradicen"}'

        async def aclose(self) -> None:
            return None

    _patch_infra(monkeypatch)
    monkeypatch.setattr(postgres_module, "insert_recommendation", fake_insert)
    monkeypatch.setattr(postgres_module, "has_pending_recommendation", fake_has_pending)
    monkeypatch.setattr(postgres_module, "recent_seed_chunks", fake_seed_chunks)
    monkeypatch.setattr(search_module, "similarity_band_chunks", fake_band)
    monkeypatch.setattr(recommend_module.neo4j_storage, "gaps_by_prerequisite", fake_gaps)
    monkeypatch.setattr(recommend_module, "OllamaLLMClient", lambda settings: _ConfirmingLLM())

    result = await recommend_module._async_recommend(
        node_ids=[], relation_ids=[], trace_id="trace-1"
    )

    assert result == _no_op_result(
        recommendations_created=1,
        contradiction_candidates_checked=1,
        contradiction_recommendations_created=1,
    )
    [call] = inserted
    assert call["type"] == "contradiction"
    assert call["confidence"] == pytest.approx(0.6)
    assert call["target_entities"] == sorted([str(seed["chunk_id"]), str(match.chunk_id)])
    assert len(call["evidence"]) == 2
    assert call["source_event_id"] == "trace-1"


async def test_async_recommend_contradiccion_no_confirmada_no_crea_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_insert(engine: Any, **kwargs: Any) -> None:
        raise AssertionError("un veredicto negativo no debe crear una recomendación")

    async def fake_gaps(driver: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    seed = _seed_chunk()
    match = _match_hit()

    async def fake_seed_chunks(engine: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [seed]

    async def fake_band(engine: Any, embedding: Any, **kwargs: Any) -> list[SearchHit]:
        return [match]

    async def fake_has_pending(engine: Any, **kwargs: Any) -> bool:
        return False

    _patch_infra(monkeypatch)  # OllamaLLMClient fake responde contradicts=false por defecto
    monkeypatch.setattr(postgres_module, "insert_recommendation", fail_insert)
    monkeypatch.setattr(postgres_module, "has_pending_recommendation", fake_has_pending)
    monkeypatch.setattr(postgres_module, "recent_seed_chunks", fake_seed_chunks)
    monkeypatch.setattr(search_module, "similarity_band_chunks", fake_band)
    monkeypatch.setattr(recommend_module.neo4j_storage, "gaps_by_prerequisite", fake_gaps)

    result = await recommend_module._async_recommend(
        node_ids=[], relation_ids=[], trace_id="trace-1"
    )

    assert result == _no_op_result(contradiction_candidates_checked=1)


async def test_async_recommend_contradiccion_sin_match_no_revisa_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_insert(engine: Any, **kwargs: Any) -> None:
        raise AssertionError("sin match en la banda no debe invocar al LLM ni crear nada")

    async def fake_gaps(driver: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    seed = _seed_chunk()

    async def fake_seed_chunks(engine: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [seed]

    async def fake_band(engine: Any, embedding: Any, **kwargs: Any) -> list[SearchHit]:
        return []

    _patch_infra(monkeypatch)
    monkeypatch.setattr(postgres_module, "insert_recommendation", fail_insert)
    monkeypatch.setattr(postgres_module, "recent_seed_chunks", fake_seed_chunks)
    monkeypatch.setattr(search_module, "similarity_band_chunks", fake_band)
    monkeypatch.setattr(recommend_module.neo4j_storage, "gaps_by_prerequisite", fake_gaps)

    result = await recommend_module._async_recommend(
        node_ids=[], relation_ids=[], trace_id="trace-1"
    )

    assert result == _no_op_result()


async def test_async_recommend_contradiccion_par_ya_pendiente_no_llama_al_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_insert(engine: Any, **kwargs: Any) -> None:
        raise AssertionError("un par ya pendiente no debe reinsertarse")

    async def fake_gaps(driver: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    seed = _seed_chunk()
    match = _match_hit()

    async def fake_seed_chunks(engine: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [seed]

    async def fake_band(engine: Any, embedding: Any, **kwargs: Any) -> list[SearchHit]:
        return [match]

    async def fake_has_pending(engine: Any, **kwargs: Any) -> bool:
        return True

    class _FailingLLM:
        async def generate(self, prompt: str, *, system: str | None = None) -> str:
            raise AssertionError("un par ya pendiente no debe llegar a llamar al LLM")

        async def aclose(self) -> None:
            return None

    _patch_infra(monkeypatch)
    monkeypatch.setattr(postgres_module, "insert_recommendation", fail_insert)
    monkeypatch.setattr(postgres_module, "has_pending_recommendation", fake_has_pending)
    monkeypatch.setattr(postgres_module, "recent_seed_chunks", fake_seed_chunks)
    monkeypatch.setattr(search_module, "similarity_band_chunks", fake_band)
    monkeypatch.setattr(recommend_module.neo4j_storage, "gaps_by_prerequisite", fake_gaps)
    monkeypatch.setattr(recommend_module, "OllamaLLMClient", lambda settings: _FailingLLM())

    result = await recommend_module._async_recommend(
        node_ids=[], relation_ids=[], trace_id="trace-1"
    )

    assert result == _no_op_result()


def test_las_tasks_estan_registradas_con_nombre_de_evento() -> None:
    assert "kos.recommend_from_graph_update" in app.tasks
    assert "kos.recommend_flush" in app.tasks


def test_recommender_agent_importado_correctamente() -> None:
    # Guardarraíl: si alguien rompe el import (ej. mueve el módulo), este test
    # falla con un mensaje claro en vez de un traceback de import en otro test.
    assert RecommenderAgent is not None
