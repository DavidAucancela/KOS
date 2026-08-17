# Retro — Sprint 22: "El grafo avisa de verdad"

**Estado:** ✅ Cerrado 2026-08-17. Primer sprint de v1.0 — Recomendador (Fase 5).

## Motivación

Al planificar v1.0 (doc 11, 2026-08-16) apareció un hallazgo que cambiaba el sprint fundacional:
`GraphUpdated` (`kos_core/schemas/events.py`) decía en su propio docstring "emitido por
`kos.graph_sync`" — pero `kos.graph_sync` nunca publicaba el evento. Solo las correcciones
manuales de grafo (`PATCH`/`DELETE /v1/graph/*`, Sprint 9) lo emitían. La deuda registrada desde
Sprint 9 ("nadie consume `graph.updated`") era en realidad doble: el camino automático tampoco lo
emitía. Este sprint resuelve ambas mitades antes de construir ningún tipo de recomendación real
sobre el evento.

## Decisiones de alcance (doc 11 §3, tomadas al planificar v1.0)

- Entrega vía **tasks de Celery encadenados**, no suscripción al canal pub/sub `kos:events` — un
  consumidor suscripto directo perdería eventos publicados mientras el proceso no está corriendo
  (mismo problema que doc 04 §1.1 ya resolvió para memoria).
- **Debounce**: una resincronización real del vault puede tocar decenas de nodos en segundos: se
  acumulan en Redis y se dispara una sola pasada del Recomendador por ventana (`DEBOUNCE_SECONDS`),
  no una por nodo.
- El Recomendador de este sprint es un **esqueleto**: no decide qué recomendar todavía (eso es
  Sprint 23/24) — solo prueba que el cableado disparador → agente → Postgres funciona de punta a
  punta con una recomendación placeholder.

## Qué se construye

- **`kos_core/schemas/recommendations.py`** (nuevo): `Recommendation`, `RecommendationType`
  (`gap`|`contradiction`|`related_relation`|`roadmap`|`reorganization`), `RecommendationStatus`
  (doc 11 §2).
- **Migración `0009_recommendations.py`** + `postgres.py` (`recommendations_table`,
  `insert_recommendation`).
- **`packages/mcp-tools/.../tools/recommendations.py`** (nuevo): `recommendations.store`,
  herramienta de escritura con el mismo gate de `permissions.py` que `memory.store` —
  `WRITE_TOOLS` suma `"recommendations.store"`.
- **`packages/agents/src/kos_agents/recommender.py`** (nuevo): `RecommenderAgent` — persiste vía
  `recommendations.store`, forzando `confirm=True` por su cuenta (mismo espíritu que
  `LearningAgent`: el sistema completando un paso ya decidido, no un LLM autónomo). No entra al
  catálogo del Planner ni a `Plan.steps`/`Plan.post` — no resuelve consultas del usuario.
- **`apps/workers/.../tasks/recommend.py`** (nuevo): `kos.recommend_from_graph_update` (acumula
  `node_ids`/`relation_ids` en Redis y reprograma `kos.recommend_flush` con un token nuevo cada
  vez — debounce clásico) y `kos.recommend_flush` (solo ejecuta si su token sigue vigente;
  cualquier disparo posterior lo supera y queda como no-op). `_async_recommend` construye el
  `RecommenderAgent` real sobre un servidor MCP embebido, mismo patrón que `kos.memory_learn`
  desde Sprint 21.
- **`kos.graph_sync`**: ahora encadena `kos.recommend_from_graph_update` cuando sincronizó nodos
  reales — la mitad que faltaba del hallazgo de arriba. `_sync_graph` devuelve `node_ids` en su
  resultado.
- **`apps/api/.../routes/graph.py`**: las tres correcciones manuales (`PATCH nodes`,
  `PATCH`/`DELETE relations`) encadenan el mismo task vía `graph_service.enqueue_recommend`
  (encola por nombre de task, mismo patrón que `source_service.enqueue_sync` — la API no importa
  `kos_workers`, doc 09 §2), sin reemplazar `publish_event` existente.

## Verificación

Contra infra real (`make up`, Postgres/Neo4j/Redis reales, migración `0009` aplicada con
`alembic upgrade head`): se invocó `recommend_from_graph_update` y `recommend_flush` directo
(sin worker de Celery corriendo, llamando `.run()`) con un `node_id` sintético — escribió una fila
real en `recommendations` (`type=gap`, `status=pending`, `target_entities=["smoke-test-node-1"]`),
confirmada por `SELECT` directo en `kos-postgres` y luego eliminada (era un smoke test, no una
recomendación real). Cableado disparador → agente → MCP → Postgres verificado de punta a punta.

349 tests unitarios (16 nuevos: `test_recommender_agent.py`, `test_recommendations_tools.py`,
`test_recommend_task.py`, 2 nuevos en `test_graph_sync_task.py`, `_no_real_celery_enqueue` en
`test_routes_graph.py`), ruff, `mypy --strict` (core), import-linter y `ruff format` limpios.

## Qué se recorta (deuda visible)

- El placeholder que escribe este sprint (`type="gap"`, confidence 0.0, título fijo) no es una
  recomendación real — Sprint 23 lo reemplaza con lógica de reglas/consultas de grafo sobre
  `PREREQUISITE_OF`/`KNOWS`.
- El debounce agrupa dentro de un único proceso worker vía Redis (sets + token) — no se probó
  contra concurrencia real de múltiples workers disparando `graph.updated` a la vez; suficiente
  para el volumen de un side-project de un solo usuario, no diseñado para escala mayor.
- `relation_ids` del camino automático (`kos.graph_sync`) queda siempre vacío — el sync no
  escribe relaciones nuevas que ameriten pasarlas todavía; las correcciones manuales sí las
  incluyen.

## Qué se aprendió

- El hallazgo del docstring desalineado con el código (`GraphUpdated` prometía una emisión que
  nunca ocurrió) solo apareció al escribir el documento de diseño de v1.0, no durante ningún
  sprint anterior — otra confirmación de que "docs antes que código" también sirve para auditar
  código ya escrito, no solo para planificar el nuevo.
- El patrón de debounce con token en Redis (reemplazar el token en cada disparo, que el flush
  verifique vigencia antes de ejecutar) es reutilizable para cualquier evento futuro que necesite
  agruparse — no quedó acoplado a `graph.updated` específicamente.
