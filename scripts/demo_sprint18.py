"""Demo del Sprint 18 (doc 08): "el planner decide".

Tres escenarios contra infra real: (1) una pregunta que se beneficia de
contexto del grafo genera un plan dinámico con un paso `graph`; (2) una
pregunta puramente factual reduce a retrieval→writing (2 pasos, elegido por
el LLM, no hardcodeado); (3) un LLM roto para la generación de planes
demuestra la caída al plan fijo (`degraded=true`) sin romper la respuesta —
la síntesis sigue usando el LLM real.

Requisitos: `make up`, `make pull-models`, `make migrate`, Ollama nativo con
el vault ya sincronizado, y la API real corriendo (`make dev-api`).
Uso: `uv run python scripts/demo_sprint18.py`.
"""

import asyncio

import httpx

from kos_agents.graph import GraphAgent
from kos_agents.planner.planner import Planner
from kos_agents.retrieval import RetrievalAgent
from kos_agents.writing import WritingAgent
from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient, OllamaLLMClient
from kos_core.schemas.plan import PlanRequest
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_mcp.client import EmbeddedToolCaller
from kos_mcp.server import AppContext, create_server

API_URL = "http://localhost:8000/v1/query"


async def _demo_via_api(query: str, label: str) -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(API_URL, json={"query": query})
    response.raise_for_status()
    body = response.json()
    plan_shape = [(step["id"], step["agent"]) for step in body["plan"]]
    print(f"✓ {label}: plan={plan_shape}, degraded={body['degraded']}")


class _BrokenPlannerLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt: str, **kwargs: object) -> str:
        self.calls += 1
        return "esto no es JSON válido para nada"


async def _demo_fallback_standalone() -> None:
    settings = get_settings()
    engine = postgres_storage.create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)
    llm = OllamaLLMClient(settings)
    app_context = AppContext(
        settings=settings, postgres_engine=engine, neo4j_driver=driver, embedding_client=embedder
    )
    server = create_server(app_context)
    try:
        async with EmbeddedToolCaller(server) as caller:
            broken_llm = _BrokenPlannerLLM()
            planner = Planner(
                llm=broken_llm,
                retrieval_agent=RetrievalAgent(caller),
                graph_agent=GraphAgent(caller),
                writing_agent=WritingAgent(llm),  # síntesis con el LLM real
            )
            plan, _responses = await planner(
                PlanRequest(query="¿qué es FastAPI?", trace_id="demo-sprint18-fallback")
            )
            print(
                f"✓ Fallback (LLM de planificación roto): degraded={plan.degraded}, "
                f"plan={[(s.id, s.agent) for s in plan.steps]}, "
                f"intentos de generación={broken_llm.calls}"
            )
    finally:
        await engine.dispose()
        await driver.close()
        await embedder.aclose()
        await llm.aclose()


async def main() -> None:
    try:
        await _demo_via_api(
            "¿qué tecnologías están más relacionadas entre sí en mi base de conocimiento?",
            "pregunta con contexto de grafo",
        )
        await _demo_via_api("¿qué es FastAPI?", "pregunta puramente factual")
    except httpx.ConnectError:
        print("○ API no está corriendo en :8000 — saltando los dos primeros escenarios")
    await _demo_fallback_standalone()


if __name__ == "__main__":
    asyncio.run(main())
