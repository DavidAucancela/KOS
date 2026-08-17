# Retro — Sprint 23: "Lagunas de conocimiento"

**Estado:** ✅ Cerrado 2026-08-17. Segundo sprint de v1.0 — Recomendador (Fase 5).

## Motivación

Sprint 22 dejó el cableado disparador→agente→Postgres funcionando, pero con un placeholder fijo
(`type="gap"`, confidence 0.0, título genérico) en cada pasada. Este sprint reemplaza ese
placeholder por el primer tipo de recomendación real: lagunas de conocimiento.

## Decisiones de alcance (tomadas con el usuario al planificar)

- **Sin `KNOWS`/`Person` real.** Doc 02 §3.2 define `KNOWS` como `Person(usuario) →
  Skill/Technology/Concept`, y doc 11 §4 proponía "laguna = `PREREQUISITE_OF` sin `KNOWS`
  correspondiente". Investigar el código confirmó que **nunca se creó ningún nodo que represente
  al usuario ni ninguna arista `KNOWS`** — `Person` en la ontología es un tipo genérico para gente
  mencionada en las notas (autores, colegas), no "vos". Redefinición operable adoptada: una laguna
  es un nodo `PREREQUISITE_OF` de algo **débilmente evidenciado** (`confidence < 0.5`, el mismo
  umbral que doc 02 §4 regla 4 ya usa para decidir qué mostrar en la UI) — sin inventar conceptos
  nuevos, calculable con lo que el grafo ya tiene. Crear un nodo "vos" + poblar `KNOWS` de verdad
  queda como deuda documentada para cuando haya un caso de uso concreto.
- **Sin plantilla pública de `graph.query`.** Doc 08 preveía "nueva plantilla de `graph.query`"
  (superficie `POST /v1/graph/query`, doc 06 §2). El único consumidor real
  (`RecommenderAgent`/`kos.recommend_from_graph_update`) llama a `kos_core.storage.neo4j` directo,
  nunca vía la API HTTP — mismo patrón que `kos.memory_learn` desde Sprint 21. Se implementó como
  función nueva de `kos_core.storage.neo4j` (mismo nivel que `most_connected_nodes`), no como
  plantilla pública sin consumidor.

## Qué se construye

- **`kos_core/storage/neo4j.py`**: `gaps_by_prerequisite()` — nodos `PREREQUISITE_OF` con
  `confidence` bajo `GAP_CONFIDENCE_THRESHOLD` (0.5), devolviendo `node_id`, `name`, `confidence`
  y `blocks` (a qué bloquea), ordenados por `confidence` ascendente (los más débiles primero).
- **`kos_core/storage/postgres.py`**: `has_pending_recommendation()` (guardarraíl contra
  duplicados — sin esto, cada `graph.updated` reinsertaría la misma laguna) y
  `list_recommendations()` (mismo patrón de cursor que `list_memories`).
- **`apps/workers/.../tasks/recommend.py`**: `_async_recommend` reemplaza el placeholder de
  Sprint 22 por lógica real: consulta `gaps_by_prerequisite`, salta candidatos ya `pending`, arma
  un `AgentRequest` por candidato nuevo (`confidence = 1.0 - confidence_del_nodo`,
  `priority = cantidad de cosas que bloquea`), invoca `RecommenderAgent` una vez por candidato,
  tope de `MAX_GAP_RECOMMENDATIONS_PER_RUN = 5` por pasada.
- **`GET /v1/recommendations?type=&status=`** (nuevo): `apps/api/.../routes/recommendations.py` +
  `services/recommendation_service.py`, mismo patrón que `routes/memory.py`. Reusa el schema
  `Recommendation` (Sprint 22) directo, sin un `RecommendationOut` separado — no tiene computed
  fields.

`RecommenderAgent` y la tool MCP `recommendations.store` (ambos de Sprint 22) no cambiaron — ya
eran genéricos sobre `type`/`title`/etc.

## Verificación

Contra infra real (`make up`, sin mocks): se crearon dos nodos `Concept` reales en Neo4j (uno con
`confidence=0.2` prerrequisito del otro) y se invocó `_async_recommend` directo — encontró 1
candidato, creó 1 recomendación real (`confidence=0.8`, `priority=1`, título
`"Posible laguna: Smoke Weak Concept"`), confirmada por `SELECT` en `kos-postgres` y luego
eliminada junto con los nodos de prueba (era un smoke test, no una laguna real del vault).

356 tests unitarios (23 nuevos: `test_recommend_task.py` reescrito para lógica real, 6 tests de
integración nuevos contra Neo4j/Postgres reales — `test_neo4j_gaps_integration.py`,
`test_postgres_recommendations.py` —, `test_routes_recommendations.py`), ruff, `mypy --strict`
(core), import-linter y `ruff format` limpios.

## Qué se recorta (deuda visible)

- No existe un nodo "vos" ni `KNOWS` real — `confidence` del nodo es el proxy de "poco
  evidenciado". Si en algún momento aparece un caso de uso real (ej. marcar manualmente qué se
  sabe), esto necesita revisarse desde cero, no es una extensión trivial del proxy actual.
- `gaps_by_prerequisite` no acota por vecindad del cambio (`node_ids`/`relation_ids` del disparo
  debounced) — recorre el grafo completo en cada pasada. Aceptable para el volumen de un vault de
  un solo usuario; no diseñado para escala mayor.
- El tope de 5 recomendaciones por pasada es arbitrario, sin datos reales de uso que lo justifiquen.
- Dedup solo cubre "ya hay una `pending` con la misma firma" — el dedup completo contra
  recomendaciones ya `dismissed` (para no regenerar algo que el usuario descartó) es Sprint 25
  (doc 11 §8), explícitamente fuera de este sprint.

## Nota al margen: mismo bug de siempre, otra vez

Al correr la suite de integración completa para verificar el cierre, apareció
`test_list_tools_expone_las_7_herramientas` (renombrado en la auditoría de cierre de v0.5,
2026-08-16) desactualizado de nuevo: Sprint 22 sumó `recommendations.store` al servidor MCP sin
tocar este test — exactamente el mismo patrón que ya rompió una vez con Sprint 20 (deuda ya
documentada). Corregido acá, con una nota en el propio test para que la próxima tool nueva no
repita el patrón por tercera vez.

## Qué se aprendió

- El hallazgo del nodo "vos" faltante solo apareció investigando el código antes de escribir la
  query — confirma otra vez que "docs antes que código" también sirve para detectar promesas de
  diseño que nunca se implementaron, no solo para planificar trabajo nuevo.
- Reusar el umbral de confianza ya establecido en doc 02 §4 (0.5, "mostrar") como proxy de "laguna"
  evitó inventar un concepto nuevo — la redefinición quedó anclada a una regla que el sistema ya
  respetaba en otro contexto (la UI), no a un número arbitrario nuevo.
