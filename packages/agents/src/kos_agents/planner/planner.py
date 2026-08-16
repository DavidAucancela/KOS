"""Planner real (doc 03 §3/§5, Sprint 18): reemplaza el pipeline fijo de
`/v1/query` — le pide al LLM un plan en JSON eligiendo entre `retrieval`/`graph`
como pasos de evidencia y siempre cerrando en `writing`. Si la generación falla
o el JSON no valida tras un reintento, cae al plan fijo retrieval→writing de
Sprint 17 (doc 03 §3 regla 4, algoritmo documentado en `docs/03-...md`).

Parseo tolerante: mismo patrón que `s7_entities`/`s8_relations`
(`kos_core.json_utils.strip_code_fence` + `json.loads` + validación Pydantic que
descarta lo que no valida en vez de fallar el pipeline entero) — no depende del
`format="json"` nativo de Ollama, nunca usado en este repo; con modelos locales
chicos (`llama3.2`) un parser tolerante + reintento es más confiable que confiar
en que el modelo respete JSON-mode.

Catálogo de agentes de este sprint: `retrieval` (búsqueda sobre las notas) y
`graph` acotado a las plantillas que no requieren resolver un node_id por
nombre primero (`query` con `template=most_connected|nodes_by_type`) —
`get_node`/`find_path` necesitarían un paso previo de resolución de entidades
por nombre, fuera de alcance de este sprint (deuda anotada en la retro).
`memory` queda deliberadamente fuera del catálogo hasta Sprint 21."""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import ValidationError

from kos_agents.base import Agent
from kos_agents.planner.executor import execute_plan
from kos_core.json_utils import strip_code_fence
from kos_core.llm.base import LLMClient
from kos_core.schemas.agents import AgentResponse
from kos_core.schemas.plan import Plan, PlanRequest, PlanStep

_CATALOG = (
    'agent="retrieval": busca evidencia en las notas del usuario (búsqueda híbrida). '
    'inputs: {"query": str, "mode"?: "hybrid"|"lexical"|"vector", "limit"?: int}.\n'
    'agent="graph": consulta el grafo de conocimiento sin necesitar un id de nodo '
    "específico (nodos más conectados, o nodos de un tipo dado). "
    'inputs: {"template": "most_connected"|"nodes_by_type", "node_type"?: str, "limit"?: int}.\n'
    'agent="writing": redacta la respuesta final citando la evidencia de los pasos '
    "de los que depende. Siempre debe existir exactamente un paso `writing` al final "
    "del plan, dependiendo de todos los pasos de evidencia que uses."
)

_PLANNER_SYSTEM = (
    "Eres el planner de KOS: descompones una pregunta en un plan de pasos JSON. "
    "Herramientas disponibles:\n" + _CATALOG + "\n\n"
    "Reglas: usa 1 o 2 pasos de evidencia (retrieval y/o graph) según lo que la "
    "pregunta necesite — no uses graph si la pregunta no pide relaciones/contexto "
    "del grafo. Los pasos sin dependencias entre sí se ejecutan en paralelo. "
    "Devuelve SOLO un JSON: una lista de objetos "
    '{"id": str, "agent": str, "task": str (descripción breve), '
    '"inputs": object, "depends_on": [str]}. Nada de texto fuera del JSON.'
)

_MAX_ATTEMPTS = 2
_ALLOWED_AGENTS = frozenset({"retrieval", "graph", "writing"})


def _fixed_plan_steps(query: str, *, mode: str, limit: int) -> list[PlanStep]:
    """Plan fijo retrieval→writing de Sprint 17 — red de seguridad si el
    Planner no puede generar/validar un plan dinámico (doc 03 §3 regla 4)."""
    return [
        PlanStep(
            id="s1",
            agent="retrieval",
            task=f"buscar evidencia para: {query}",
            inputs={"query": query, "mode": mode, "limit": limit},
        ),
        PlanStep(
            id="s2",
            agent="writing",
            task="redactar la respuesta con citas a partir de la evidencia",
            depends_on=["s1"],
        ),
    ]


def _validate_steps(raw: Any, *, query: str) -> list[PlanStep] | None:
    """Valida la lista de pasos propuesta por el LLM; `None` si no es
    aprovechable (dispara reintento o fallback)."""
    if not isinstance(raw, list) or not raw:
        return None

    steps: list[PlanStep] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        try:
            step = PlanStep.model_validate(item)
        except ValidationError:
            return None
        if step.agent not in _ALLOWED_AGENTS:
            return None
        steps.append(step)

    ids = {step.id for step in steps}
    for step in steps:
        if not set(step.depends_on) <= ids - {step.id}:
            return None  # dependencia a un id inexistente o a sí mismo

    writing_steps = [step for step in steps if step.agent == "writing"]
    if len(writing_steps) != 1 or not writing_steps[0].depends_on:
        return None  # exactamente un paso writing, dependiendo de algo

    return steps


def parse_plan_response(raw_json: str, *, query: str) -> list[PlanStep] | None:
    """Parsea y valida la respuesta del LLM; tolerante a JSON malformado
    (mismo estilo que `s7_entities.parse_entities_response`)."""
    try:
        parsed = json.loads(strip_code_fence(raw_json))
    except json.JSONDecodeError:
        return None
    return _validate_steps(parsed, query=query)


class Planner:
    def __init__(
        self,
        *,
        llm: LLMClient,
        retrieval_agent: Agent,
        graph_agent: Agent,
        writing_agent: Agent,
    ) -> None:
        self._llm = llm
        self._registry: dict[str, Agent] = {
            "retrieval": retrieval_agent,
            "graph": graph_agent,
            "writing": writing_agent,
        }

    async def _generate_steps(self, request: PlanRequest) -> tuple[list[PlanStep], bool]:
        """Intenta generar un plan dinámico hasta `_MAX_ATTEMPTS` veces; si
        falla, devuelve el plan fijo con `degraded=True`."""
        prompt = f"Pregunta del usuario: {request.query!r}"
        last_error: str | None = None
        for _attempt in range(_MAX_ATTEMPTS):
            full_prompt = (
                prompt if last_error is None else f"{prompt}\n\nError anterior: {last_error}"
            )
            try:
                raw = await self._llm.generate(full_prompt, system=_PLANNER_SYSTEM)
            except Exception as exc:  # cualquier fallo del LLM dispara fallback
                last_error = str(exc)
                continue
            steps = parse_plan_response(raw, query=request.query)
            if steps is not None:
                return steps, False
            last_error = "el plan no validó contra el esquema esperado"
        return _fixed_plan_steps(request.query, mode=request.mode, limit=request.limit), True

    async def __call__(self, request: PlanRequest) -> tuple[Plan, dict[str, AgentResponse]]:
        steps, degraded = await self._generate_steps(request)
        degraded_reason: str | None = "llm_generation" if degraded else None

        # Presupuesto de pasos (doc 03 §3 regla 4, Sprint 19): un plan dinámico
        # con más pasos de los permitidos degrada al plan fijo en vez de
        # ejecutarse tal cual — misma red de seguridad que un fallo de
        # generación, no un podador nuevo.
        max_steps = request.constraints.max_steps
        if max_steps is not None and len(steps) > max_steps:
            steps = _fixed_plan_steps(request.query, mode=request.mode, limit=request.limit)
            degraded = True
            degraded_reason = "budget_max_steps"

        responses = await execute_plan(
            steps,
            self._registry,
            query=request.query,
            trace_id=request.trace_id,
            constraints=request.constraints,
            timeout_s=request.constraints.timeout_s,
        )

        enriched: list[PlanStep] = []
        for step in steps:
            response = responses.get(step.id)
            if response is None:
                enriched.append(step)
                continue
            enriched.append(
                step.model_copy(
                    update={
                        "evidence_count": len(response.evidence),
                        "confidence": response.confidence,
                        "cost": response.cost,
                    }
                )
            )

        # Presupuesto de tiempo excedido (Sprint 19): quedaron pasos sin
        # correr porque `execute_plan` cortó al tope de una oleada, no porque
        # una dependencia nunca resolviera (eso ya lo cubre `step_degraded`
        # más abajo vía `outputs["degraded"]` de cada agente).
        budget_timeout = len(responses) < len(steps)

        # Un paso individual (ej. retrieval degradando a léxica por fallo del
        # embedder, doc 06) también cuenta como plan degradado — no solo el
        # fallback de generación de este Planner.
        step_degraded = any(bool(r.outputs.get("degraded", False)) for r in responses.values())

        # Prioridad si coexisten varias causas: presupuesto > step_failure >
        # llm_generation — la causa más externa es la más útil al inspeccionar.
        if budget_timeout:
            degraded_reason = "budget_timeout"
        elif degraded_reason == "budget_max_steps":
            pass
        elif step_degraded:
            degraded_reason = "step_failure"

        plan = Plan(
            plan_id=uuid.uuid4(),
            query=request.query,
            steps=enriched,
            degraded=degraded or step_degraded or budget_timeout,
            degraded_reason=degraded_reason,
            trace_id=request.trace_id,
        )
        return plan, responses
