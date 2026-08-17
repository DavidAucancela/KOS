"""Tasks del Recomendador (Sprint 22, doc 11 §3): `graph.updated` deja de ser
huérfano.

`kos.recommend_from_graph_update` es el punto de entrada — lo encadena
`kos.graph_sync` (sync automático) y lo encolan las correcciones manuales de
grafo (`PATCH`/`DELETE /v1/graph/*`, `apps/api/.../routes/graph.py`). No
ejecuta el Recomendador de inmediato: acumula `node_ids`/`relation_ids` en
Redis y reprograma `kos.recommend_flush` con un `token` nuevo cada vez
(debounce clásico) — una resincronización real del vault puede tocar decenas
de nodos en segundos, y sin agrupar se dispararía una pasada del Recomendador
por nodo individual (doc 11 §3.2). Solo el `flush` cuyo token siga siendo el
vigente en Redis al cumplirse `DEBOUNCE_SECONDS` ejecuta de verdad; cualquier
`flush` más viejo, superado por un disparo posterior, es un no-op.

`_async_recommend` construye el `RecommenderAgent` real (vía servidor MCP
embebido, mismo patrón que `kos.memory_learn` desde Sprint 21). Sprint 23
reemplaza el placeholder de Sprint 22 por el primer tipo real: lagunas de
conocimiento (`gaps_by_prerequisite`, doc 11 §4/§5) — nodos `PREREQUISITE_OF`
débilmente evidenciados en el vault. Sin `KNOWS`/`Person` real todavía
(decisión explícita al planificar el sprint: no existe un nodo que represente
"el usuario", ver docs/deuda-tecnica.md) — `confidence` del propio nodo es el
proxy. `contradiction` (Sprint 24) se suma con la misma forma: encontrar
candidatos por consulta de grafo, invocar `RecommenderAgent` una vez por
candidato nuevo."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from kos_agents.recommender import RecommenderAgent
from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.schemas.agents import AgentRequest
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_core.storage import redis as redis_storage
from kos_core.storage.postgres import create_engine
from kos_mcp.client import EmbeddedToolCaller
from kos_mcp.server import AppContext as MCPAppContext
from kos_mcp.server import create_server as create_mcp_server
from kos_workers.celery_app import app

# Ventana de agrupamiento (doc 11 §3.2): parámetro de un algoritmo, no
# configuración de despliegue — mismo criterio que `SIMILARITY_THRESHOLD`
# (graph_sync.py) y `DUPLICATE_THRESHOLD` (tasks/memory.py).
DEBOUNCE_SECONDS = 20

_PENDING_NODES_KEY = "kos:recommend:pending_nodes"
_PENDING_RELATIONS_KEY = "kos:recommend:pending_relations"
_FLUSH_TOKEN_KEY = "kos:recommend:flush_token"

# Tope por pasada (Sprint 23): evita que una resincronización grande del
# vault genere una ráfaga de decenas de recomendaciones de una sola vez —
# mismo espíritu que los demás límites fijos en código de este dominio
# (DEBOUNCE_SECONDS acá mismo, SIMILARITY_THRESHOLD en graph_sync.py).
MAX_GAP_RECOMMENDATIONS_PER_RUN = 5


def _decode(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


def _gap_agent_request(candidate: dict[str, Any], *, trace_id: str) -> AgentRequest:
    name = candidate["name"] or candidate["canonical_name"]
    blocks: list[str] = candidate["blocks"]
    confidence = float(candidate["confidence"])
    blocked_text = ", ".join(blocks) if blocks else "otros conceptos del grafo"
    return AgentRequest(
        task="laguna de conocimiento por PREREQUISITE_OF débilmente evidenciado (doc 11 §4)",
        inputs={
            "type": "gap",
            "title": f"Posible laguna: {name}",
            "description": (
                f"'{name}' es prerrequisito de {blocked_text} pero tiene poca evidencia en "
                f"tu vault (confidence={confidence:.2f}) — revisalo o documentalo mejor."
            ),
            "target_entities": [candidate["node_id"]],
            "confidence": round(1.0 - confidence, 2),
            "priority": len(blocks),
            "source_event_id": trace_id,
        },
        trace_id=trace_id,
    )


async def _async_recommend(
    *, node_ids: list[str], relation_ids: list[str], trace_id: str
) -> dict[str, Any]:
    """Busca candidatos de laguna de conocimiento (`gaps_by_prerequisite`, doc
    11 §4/§5) y persiste uno por candidato nuevo (no ya `pending`) vía el
    `RecommenderAgent` real sobre un servidor MCP embebido (mismo patrón que
    `kos.memory_learn`, Sprint 21). `node_ids`/`relation_ids` (el disparo que
    debounceó hasta acá) no acotan la búsqueda todavía — el grafo entero es
    chico para un vault de un solo usuario; acotar por vecindad del cambio
    queda para cuando el volumen lo justifique."""
    settings = get_settings()
    engine = create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)
    try:
        candidates = await neo4j_storage.gaps_by_prerequisite(driver)
        mcp_context = MCPAppContext(
            settings=settings,
            postgres_engine=engine,
            neo4j_driver=driver,
            embedding_client=embedder,
        )
        server = create_mcp_server(mcp_context)
        created: list[str] = []
        async with EmbeddedToolCaller(server) as caller:
            agent = RecommenderAgent(caller)
            for candidate in candidates:
                if len(created) >= MAX_GAP_RECOMMENDATIONS_PER_RUN:
                    break
                target_entities = [candidate["node_id"]]
                if await postgres_storage.has_pending_recommendation(
                    engine, type="gap", target_entities=target_entities
                ):
                    continue
                response = await agent(_gap_agent_request(candidate, trace_id=trace_id))
                recommendation_id = response.outputs.get("recommendation_id")
                if recommendation_id is not None:
                    created.append(str(recommendation_id))
        return {"candidates_found": len(candidates), "recommendations_created": len(created)}
    finally:
        await embedder.aclose()
        await driver.close()
        await engine.dispose()


@app.task(name="kos.recommend_from_graph_update")
def recommend_from_graph_update(
    *, node_ids: list[str], relation_ids: list[str], trace_id: str | None = None
) -> dict[str, Any]:
    """Punto de entrada de `graph.updated` (doc 11 §3): acumula en Redis y
    reprograma el flush debounced en vez de correr el Recomendador de inmediato."""
    settings = get_settings()
    redis_client = redis_storage.create_sync_client(settings)
    try:
        if node_ids:
            redis_client.sadd(_PENDING_NODES_KEY, *node_ids)
        if relation_ids:
            redis_client.sadd(_PENDING_RELATIONS_KEY, *relation_ids)
        token = str(uuid.uuid4())
        redis_client.set(_FLUSH_TOKEN_KEY, token)
    finally:
        redis_client.close()
    recommend_flush.apply_async(
        kwargs={"token": token, "trace_id": trace_id}, countdown=DEBOUNCE_SECONDS
    )
    return {"scheduled": True, "token": token}


@app.task(name="kos.recommend_flush")
def recommend_flush(*, token: str, trace_id: str | None = None) -> dict[str, Any]:
    """Ejecuta el Recomendador solo si `token` sigue siendo el último
    programado — cualquier disparo de `graph.updated` posterior lo reemplaza
    y este flush queda superado (no-op), mismo espíritu que `Plan.degraded`:
    preferir no duplicar antes que arriesgar trabajo repetido."""
    settings = get_settings()
    redis_client = redis_storage.create_sync_client(settings)
    try:
        current_token = redis_client.get(_FLUSH_TOKEN_KEY)
        if current_token is None or _decode(current_token) != token:
            return {"superseded": True, "recommendation_id": None}
        node_ids = sorted(_decode(v) for v in redis_client.smembers(_PENDING_NODES_KEY))
        relation_ids = sorted(_decode(v) for v in redis_client.smembers(_PENDING_RELATIONS_KEY))
        redis_client.delete(_PENDING_NODES_KEY, _PENDING_RELATIONS_KEY, _FLUSH_TOKEN_KEY)
    finally:
        redis_client.close()

    if not node_ids and not relation_ids:
        return {"superseded": False, "recommendation_id": None}

    result = asyncio.run(
        _async_recommend(
            node_ids=node_ids, relation_ids=relation_ids, trace_id=trace_id or str(uuid.uuid4())
        )
    )
    return {"superseded": False, **result}
