# Retro — Sprint 14: "La confianza se ajusta"

**Estado:** ✅ Cerrado 2026-08-15. Continúa v0.4 — Memoria y aprendizaje (Fase 3), sobre la
revisión de doc 04 §5 del 2026-08-13 (fórmula de recálculo, esquema de `source_confidences[]`,
umbral de poda, decididos con el usuario).

## Motivación

Doc 04 §5 documentaba la regla cualitativa "fuente eliminada → recálculo con la evidencia
restante" desde Sprint 11 sin una fórmula concreta ni forma de guardar el dato que hacía falta
para aplicarla — `sources[]` era una lista plana de `doc_id`, sin la confidence con la que se
agregó cada una. Sprint 11 (grafo) y Sprint 12 (memoria) heredaron la misma deuda. Este sprint
cierra ambas a la vez con la misma fórmula.

## Qué se construye

- **`packages/core/src/kos_core/confidence.py`** (nuevo): `ALIAS_BOOST` (0.05) y
  `PRUNE_THRESHOLD` (0.3) — antes `ALIAS_BOOST` vivía en `apps/workers/pipeline/s9_confidence.py`
  (capa equivocada para algo que `storage/neo4j.py` y `storage/postgres.py` también necesitan,
  ADR-0001). `s9_confidence.py` ahora lo reexporta desde acá.
- **Grafo (Neo4j)**: `source_confidences[]`, array paralelo a `sources[]` (Neo4j no admite listas
  de objetos como propiedad) en `merge_node`/`merge_relation`. `graph_sync.py` fusiona ambos
  arrays a la vez (`_merge_source_confidences`), con fallback a la confidence agregada para
  fuentes de antes de este sprint (no hizo falta backfill: el fallback resuelve los 2278 nodos
  reales que no tenían el campo). `_retire_document_nodes`/`_retire_document_relations` recalculan
  `confidence = min(1.0, max(confidence_base restante) + ALIAS_BOOST × (n_restantes − 1))` al
  perder una fuente, salvo nodos/relaciones `locked` (corrección del usuario, inmutable, doc 04 §5
  tabla).
- **Memoria (Postgres)**: `MemoryItem.sources` pasa de `list[str]` a `list[SourceRef]`
  (`{doc_id, confidence}`, JSONB admite objetos directo — sin array paralelo). Todas las fuentes
  de una memoria arrancan con la misma confidence (el dominio no tiene una señal de extracción
  por documento como el grafo). Nueva `retire_memory_sources` (contraparte de `retire_document`)
  y nueva task `kos.memory_retire_document`, encadenada desde `kos.sync_source` junto a
  `kos.graph_retire_document` — Sprint 12 nunca conectó esta propagación, no era solo la fórmula
  lo que faltaba.
- **`prune_candidate`** (computed field en `GraphNode`, `GraphRelation`, `MemoryItem`/`MemoryOut`):
  `confidence < 0.3` — umbral de alerta temprana, distinto del umbral de auto-poda por
  decaimiento (`<0.2`, doc 02 §4 regla 4).

## Verificación

Contra infra real: 11 tests de integración en `test_neo4j_integration.py` (nuevo:
recálculo de confidence al perder una fuente entre tres, dos veces seguidas; protección de
`locked`) y 5 en `test_postgres_memory.py` (nuevo: `retire_memory_sources` recalcula y archiva sin
fuentes). Demo en vivo end-to-end con datos sintéticos (sin tocar el vault real): un nodo y una
memoria con 3 fuentes (`confidence_base` 0.6/0.9/0.7) creados directo contra Neo4j/Postgres;
`kos.graph_retire_document`/`kos.memory_retire_document` disparadas por el worker Celery real
sobre la fuente de confidence 0.9; `GET /v1/graph/nodes/{id}` y `GET /v1/memory` mostraron
`confidence` bajar de 0.9 a 0.75 en ambos — exactamente `max(0.6, 0.7) + 0.05 × 1`. 246 tests
unitarios + 16 de integración nuevos/tocados, ruff y `mypy --strict` (core) limpios.

## Qué se recorta (deuda visible)

- `source_confidences[]` no se expone en la API (`GraphNode`/`GraphRelation` no lo serializan):
  es un detalle interno para el recálculo, no algo que un consumidor necesite leer. Si hiciera
  falta auditar "qué confidence tenía cada fuente" desde la API, se agrega después.
- Memoria no tiene concepto de `locked` (sin corrección manual de memoria todavía, a diferencia
  del grafo): `retire_memory_sources` siempre recalcula. No hay caso de uso real que lo pida
  todavía — se revisita si Fase 4/5 agrega corrección manual de memoria.
- `prune_candidate` es una bandera de lectura, no dispara ninguna acción todavía (no hay cola de
  revisión ni notificación). Es la base para que Sprint 15 o uno posterior la use.

## Qué se aprendió

- **El venv del proyecto se corrompió a mitad de sprint** (`ModuleNotFoundError: kos_core` en
  toda la suite, incluso fuera de pytest): correr `uv run` sin `UV_PROJECT_ENVIRONMENT` creó un
  `.venv` nuevo dentro del repo (iCloud), en vez de usar `$HOME/.venvs/kos` — exactamente la
  trampa que ya documentaba la memoria de entorno del proyecto. Se resolvió borrando el `.venv`
  local y exportando la variable en cada invocación. Los procesos de API/worker que ya estaban
  corriendo con el `.venv` roto también hubo que matarlos y reiniciarlos con el entorno correcto
  antes del demo en vivo.
- Verificar en Cypher antes de escribir el código de producción (un `cypher-shell` suelto contra
  el nodo de prueba) confirmó que `coalesce(n.source_confidences[i], ...)` no explota con
  propiedad ausente y que el `CASE` de Cypher no evalúa `apoc.coll.max` sobre una lista vacía si
  esa rama no se toma — dos supuestos que hubiera sido más caro descubrir con el test de
  integración fallando a ciegas.
- El demo en vivo con datos sintéticos (nodo/memoria creados directo, tasks disparadas por el
  worker real) prueba el cableado end-to-end sin arriesgar el vault real — mismo criterio que ya
  usa `test_neo4j_integration.py`/`test_postgres_memory.py` (canonical_names con sufijo
  aleatorio), aplicado ahora también a la verificación manual, no solo a los tests automatizados.
- `test_search_integration.py::test_busqueda_lexica_vectorial_e_hibrida` falla en este checkout
  (reproducido también en el commit base, sin este sprint) — deuda preexistente ajena a memoria/
  grafo, no se tocó.
