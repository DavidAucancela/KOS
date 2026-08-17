"""LearningAgent (doc 03 §2/§3, Sprint 21): post-paso real de aprendizaje.

Reusa `MemoryAgent.store` (Sprint 17) en vez de duplicar el mapeo a
`memory.store` — la única diferencia es que fuerza `confirm=true` por su
cuenta: es el propio sistema completando un paso ya decidido de antemano
(aprender de cada interacción respondida, doc 04 §3 paso 1), no un
agente/LLM decidiendo escribir algo nuevo de forma autónoma — mismo espíritu
que la excepción ya documentada para `/crear-nota` (doc 06 §4)."""

from __future__ import annotations

from kos_agents.base import Agent
from kos_core.schemas.agents import AgentRequest, AgentResponse


class LearningAgent:
    def __init__(self, memory_agent: Agent) -> None:
        self._memory_agent = memory_agent

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        store_request = request.model_copy(
            update={"inputs": {**request.inputs, "operation": "store", "confirm": True}}
        )
        return await self._memory_agent(store_request)
