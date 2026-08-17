"""Demo del Sprint 21 (doc 08): "aprender del plan".

Tres escenarios contra infra real: (1) `POST /v1/query` real deja un
`Plan.post` con el paso `learning` declarado (visible en `GET /v1/plans/{id}`)
y, tras esperar a que el worker de Celery lo procese, una memoria episódica
nueva escrita por el `LearningAgent` real (no por la llamada directa a
`kos_core.memory_learn` de antes) aparece en `GET /v1/memory`; (2)
`MemoryAgent.recall` standalone contra memoria real ya existente; (3) el
Planner puede elegir `memory` como paso de evidencia cuando el LLM lo decide
— se reporta si ocurrió, sin forzarlo (el LLM local no siempre lo elige).

Requisitos: `make up`, Ollama nativo, la API real corriendo (`make dev-api`)
y el worker de Celery corriendo (`make dev-workers`) para el escenario (1).
Uso: `uv run python scripts/demo_sprint21.py`.
"""

import asyncio
import uuid

import httpx

from kos_agents.memory import MemoryAgent
from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.schemas.agents import AgentRequest, Constraints
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_mcp.client import EmbeddedToolCaller
from kos_mcp.server import AppContext, create_server

API_URL = "http://localhost:8000/v1/query"
PLANS_URL = "http://localhost:8000/v1/plans"
MEMORY_URL = "http://localhost:8000/v1/memory"


async def _demo_post_learning_via_api() -> None:
    marker = uuid.uuid4().hex[:8]
    query = f"[demo-sprint21-{marker}] ¿qué es FastAPI?"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(API_URL, json={"query": query})
        response.raise_for_status()
        body = response.json()
        plan_id = body["plan_id"]

        fetched = await client.get(f"{PLANS_URL}/{plan_id}")
        fetched.raise_for_status()
        post_steps = fetched.json()["post"]
        print(f"✓ Plan.post declarado: {[(s['id'], s['agent']) for s in post_steps]}")
        assert post_steps and post_steps[0]["agent"] == "learning"

        # kos.memory_learn corre async (Celery) — esperamos a que el worker
        # real lo procese, sin bloquear /v1/query (doc 04: "la UI nunca
        # espera al aprendizaje").
        for _attempt in range(10):
            await asyncio.sleep(1.0)
            memory_response = await client.get(MEMORY_URL, params={"q": marker, "limit": 5})
            memory_response.raise_for_status()
            items = memory_response.json()["items"]
            if items:
                break
        else:
            items = []

    if items:
        print(
            f"✓ Memoria episódica escrita por el LearningAgent real: "
            f"memory_id={items[0]['memory_id']}, content={items[0]['content']!r}"
        )
    else:
        print("✗ No apareció memoria nueva — ¿está corriendo 'make dev-workers'?")


async def _demo_memory_recall_standalone() -> None:
    settings = get_settings()
    engine = postgres_storage.create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)
    app_context = AppContext(
        settings=settings, postgres_engine=engine, neo4j_driver=driver, embedding_client=embedder
    )
    server = create_server(app_context)
    try:
        async with EmbeddedToolCaller(server) as caller:
            memory_agent = MemoryAgent(caller)
            recall_response = await memory_agent(
                AgentRequest(
                    task="recordar memoria previa",
                    inputs={"operation": "recall", "limit": 5},
                    constraints=Constraints(),
                    trace_id="demo-sprint21-recall",
                )
            )
            print(f"✓ MemoryAgent.recall (standalone): {len(recall_response.evidence)} memoria(s)")
    finally:
        await engine.dispose()
        await driver.close()
        await embedder.aclose()


async def _demo_planner_elige_memory_via_api() -> None:
    query = "¿de qué temas hemos hablado antes en conversaciones previas?"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(API_URL, json={"query": query})
    response.raise_for_status()
    body = response.json()
    plan_shape = [(s["id"], s["agent"]) for s in body["plan"]]
    used_memory = any(agent == "memory" for _id, agent in plan_shape)
    print(f"✓ POST /v1/query real: plan={plan_shape}, degraded={body['degraded']}")
    print(f"  memory usado en el plan: {used_memory} (el LLM decide, no está garantizado)")


async def main() -> None:
    try:
        await _demo_post_learning_via_api()
        await _demo_planner_elige_memory_via_api()
    except httpx.ConnectError:
        print("○ API no está corriendo en :8000 — saltando los escenarios vía API")
    await _demo_memory_recall_standalone()


if __name__ == "__main__":
    asyncio.run(main())
