# Retro — Sprint 21: "Aprender del plan"

**Estado:** ✅ Cerrado 2026-08-16. Cierra v0.5 — Orquestación de agentes (Fase 4).

## Motivación

Sprint 12 (v0.4) construyó la memoria como pipeline fijo de Celery, dejando explícito en doc 04
§1.1 que Fase 4 la expondría como agentes reales sobre el mismo contrato — "un refactor de
orquestación, no una reescritura". `MemoryAgent` existía standalone desde Sprint 17 pero
`recall` nunca se conectó al Planner (deuda desde entonces), y `kos.memory_learn` seguía
llamando `kos_core.memory_learn` directo, sin pasar por MCP. Este sprint cierra ambos huecos.

## Decisiones de alcance (tomadas con el usuario al planificar)

- El post-paso de aprendizaje sigue en Celery — no se mueve a una tarea en el proceso de la API
  — pero la task construye un `LearningAgent` real vía un servidor MCP embebido en el worker.
- `memory` se suma al catálogo del Planner con el mismo patrón que `research` (Sprint 20): el
  LLM decide, no una heurística fija.
- Consumir el evento `graph.updated` (deuda desde Sprint 9) queda fuera de este sprint.

## Qué se construye

- **`packages/core/src/kos_core/schemas/plan.py`**: `Plan.post: list[PlanStep]` (nuevo campo) —
  registro declarativo de post-pasos, nunca tiene `evidence_count`/`confidence`/`cost` poblados
  porque `execute_plan` no los ejecuta.
- **Migración `0008_plan_post.py`** + `postgres.py` (`plans.post`, JSONB) + `PlanOut` en
  `routes/plans.py`: `GET /v1/plans/{id}` ahora expone `post`.
- **`packages/agents/src/kos_agents/learning.py`** (nuevo): `LearningAgent` — reusa
  `MemoryAgent.store` en vez de duplicar el mapeo a `memory.store`, forzando `confirm=true` por
  su cuenta (el sistema completando un paso ya decidido de antemano, no un agente decidiendo
  escribir algo nuevo por su cuenta — mismo espíritu que `/crear-nota`, doc 06 §4).
- **`Planner`**: suma `memory` al catálogo de evidencia (mismo patrón que `research`) y
  `_build_post_steps()` arma un paso `learning` fijo (determinístico, no elegido por el LLM) tras
  cada respuesta con síntesis exitosa. El Planner solo *declara* el post-paso; dispararlo de
  verdad sigue siendo responsabilidad de `apps/api` (`kos_agents` no depende de Celery).
- **`apps/workers/src/kos_workers/tasks/memory.py::kos.memory_learn`**: en vez de llamar
  `kos_core.memory_learn.learn_from_query_answer` directo, construye un `AppContext`/
  `create_server`/`EmbeddedToolCaller` por invocación (mismo patrón de recursos por-tarea que ya
  tenía este módulo para engine/driver) y llama al `LearningAgent` real. `apps/workers` suma
  `kos-mcp-tools`/`kos-agents` como dependencias nuevas.
- **`apps/api/.../routes/query.py`**: `MemoryAgent(caller)` conectado al `Planner` real.

## Verificación

Contra infra real en todo momento (`make up`, `make dev-api`, `make dev-workers`, sin mocks de
red ni de Celery): `scripts/demo_sprint21.py`, 3 escenarios.

1. `POST /v1/query` real deja `Plan.post = [("post-learning", "learning")]` visible en
   `GET /v1/plans/{id}`; tras esperar al worker de Celery real (sin bloquear la respuesta), una
   memoria episódica nueva aparece en `GET /v1/memory`, escrita por el `LearningAgent` real vía
   MCP — no por la llamada directa de antes.
2. Una pregunta real sobre "conversaciones previas" generó un plan con un paso `memory` elegido
   por el LLM (llama3.2 local) por su cuenta — `{"operation": "recall", "q": "KOS", "type":
   "preference", "limit": 1}` — sin resultados (no había memoria previa con ese filtro), pero el
   mecanismo completo (Planner → `MemoryAgent.recall` → MCP → evidencia) funcionó de punta a
   punta.
3. `MemoryAgent.recall` standalone contra memoria real ya existente (5 memorias de sprints
   anteriores).

320 tests unitarios (14 nuevos: `test_learning_agent.py`, 2 en `test_planner.py`, 2 refactorizados
en `test_memory_task.py`, más los de `plans.post`), ruff, `mypy --strict` (core) e import-linter
limpios.

## Qué se recorta (deuda visible)

- Consumir el evento `graph.updated` (deuda desde Sprint 9) sigue sin dueño — decisión explícita
  de dejarlo fuera de este sprint.
- El `trace_id` original de `/v1/query` no se propaga hasta el `LearningAgent`: la task de
  Celery genera uno nuevo (`uuid4()`) al invocarlo, igual que ya hacía `memory.store` cuando no
  recibía `trace_id`. Correlacionar ambos trace_id en las trazas de observabilidad queda como
  ajuste fino, sin sprint asignado.
- El catálogo `memory` del Planner solo cubre `recall` — `MemoryAgent.store` vía LLM
  (el agente decidiendo por su cuenta guardar algo distinto al aprendizaje automático de cada
  interacción) queda fuera de alcance, no tiene caso de uso real todavía.

## Qué se aprendió

- Reusar `MemoryAgent.store` desde `LearningAgent` (en vez de reimplementar el mapeo a
  `memory.store`) evitó duplicar lógica ya testeada — la única responsabilidad nueva de
  `LearningAgent` es forzar `confirm=true`, una línea de diferencia real.
- Separar "declarar el post-paso en la traza" (Planner, `kos_agents`) de "dispararlo de verdad"
  (Celery, `apps/api`) respetó la regla de dependencias de doc 09 §2 sin fricción: no hizo falta
  ningún compromiso de diseño para mantener `kos_agents` libre de Celery.
- Verificar contra infra real (worker de Celery real, no mockeado) confirmó algo que los tests
  unitarios no podían: el ciclo completo `/v1/query` → `Plan.post` declarado → Celery →
  `LearningAgent`/MCP → memoria visible en `GET /v1/memory` funciona de punta a punta, con la
  latencia real de Ollama incluida (la memoria tardó ~13s en aparecer, dentro del rango normal
  de una consulta a un LLM local).
