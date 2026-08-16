# Retro — Sprint 19: "El plan se audita"

**Estado:** ✅ Cerrado 2026-08-16. Continúa v0.5 — Orquestación de agentes (Fase 4).

## Motivación

Sprint 18 dejó el Planner generando planes dinámicos reales, pero con dos huecos marcados como
deuda explícita: `Constraints.timeout_s`/`max_steps` se pasaban por el contrato pero nunca se
exigían, y el plan generado no se persistía (`GET /v1/plans/{id}` no existía) — sin eso, un plan
solo se podía inspeccionar mientras la request estaba en vuelo. Este sprint cierra ambos huecos:
presupuestos reales con degradación observable, y persistencia auditable del plan ejecutado.

## Qué se construye

- **`packages/core/src/kos_core/alembic/versions/0007_plans.py`** (nuevo): tabla `kos.plans`
  (`plan_id`, `query`, `steps` JSONB, `degraded`, `degraded_reason`, `elapsed_ms`, `trace_id`,
  `created_at`) — el plan ejecutado completo, no solo su forma.
- **`packages/core/src/kos_core/storage/postgres.py`**: `save_plan`/`get_plan` sobre `kos.plans`.
- **`apps/api/src/kos_api/routes/plans.py`** + **`services/plan_service.py`**: `GET
  /v1/plans/{plan_id}` (doc 06 línea 59) — 404 si no existe; `POST /v1/query` ahora persiste el
  plan que ejecutó y devuelve el mismo `plan_id` en su respuesta.
- **`packages/agents/src/kos_agents/planner/executor.py`**: presupuestos reales (doc 03 §3 regla
  4). `timeout_s` se chequea al tope de cada oleada (no cancela tareas en curso — las oleadas ya
  completadas no se pierden); superarlo corta la ejecución con `degraded=true`,
  `degraded_reason="budget_timeout"`. `max_steps` recorta el plan antes de ejecutar, mismo
  `degraded_reason="budget_max_steps"`. `Constraints` (antes siempre `Constraints()` por
  defecto pese a venir en `PlanRequest.constraints` — el bug de deuda de Sprint 18) ahora se
  deriva de la request real y se propaga a cada `AgentRequest`.
- **`apps/web/src/features/traces/`** (nuevo, tercera pestaña junto a Chat/Grafo): `TracesPage` +
  `usePlan()` — UI mínima de inspección: pega un `plan_id`, muestra sus `steps` (agente, tarea,
  dependencias), `degraded`/`degraded_reason` y `elapsed_ms`.
- Doc 03 §3 regla 4 ampliada con el algoritmo concreto de presupuestos (mismo `degraded` que ya
  usaba `QueryResult` desde Sprint 4, la señal se extiende de "la generación del plan falló" a
  "la ejecución se quedó sin presupuesto").

## Verificación

Contra infra real: API real levantada (`make dev-api`), Postgres/Neo4j/Redis/MinIO/Ollama vía
`make up`. `scripts/demo_sprint19.py`, 4 escenarios:

1. `POST /v1/query` real con "¿qué es FastAPI?" → `plan_id` devuelto; `GET /v1/plans/{plan_id}`
   recupera los mismos `steps`/`degraded` que la respuesta original.
2. `GET /v1/plans/{uuid-inexistente}` → 404.
3. `timeout_s` bajo forzado a mano sobre un plan de 2 pasos dependientes → corta tras la primera
   oleada, `degraded=True`, `degraded_reason="budget_timeout"`, solo `s1` completado.
4. `max_steps` bajo forzado a mano → `degraded=True`, `degraded_reason="budget_max_steps"`.

294 tests unitarios pasan (`uv run pytest -q`); 33/34 de integración pasan contra infra real — el
1 que falla (`test_busqueda_lexica_vectorial_e_hibrida`) es el fallo preexistente ya registrado en
`docs/deuda-tecnica.md` ("Operativa — sin dueño"), no una regresión de este sprint. Ruff,
`mypy --strict` (core) e import-linter limpios.

## Qué se recorta (deuda visible)

- Sin corrección manual de deuda nueva — los dos ítems que este sprint tenía asignados
  (presupuestos, persistencia) se resolvieron completos, sin recorte de alcance.
- La UI de trazas es mínima a propósito (pegar un `plan_id` a mano): sin listado de planes
  recientes ni enlace directo desde el Chat al plan que generó una respuesta — no bloqueaba la
  demo, candidato a ajuste fino sin sprint asignado.

## Qué se aprendió

- El mismo patrón de Sprints 4/11 (`degraded` como señal única y reusada, no un campo nuevo por
  cada forma de fallo parcial) se sostuvo bien acá: extenderlo de "la generación del plan falló"
  a "el presupuesto se agotó en ejecución" no pidió ningún cambio de esquema, solo un
  `degraded_reason` más específico.
- Cortar `timeout_s` al tope de la oleada (no cancelar tareas en curso) fue la decisión correcta
  de simplicidad: cancelar `asyncio.gather` a mitad de oleada hubiera dejado agentes a medio
  ejecutar sin una forma limpia de descartar su resultado parcial, y el costo de esperar a que
  termine la oleada en curso es acotado (el `timeout_s` es un presupuesto, no un límite duro de
  wall-clock).
