# Retro — Sprint 13: "La memoria conoce el grafo"

**Estado:** ✅ Cerrado 2026-08-14. Continúa v0.4 — Memoria y aprendizaje (Fase 3), sobre la
revisión de doc 04 §2 del mismo día (entity-linking decidido sin extracción LLM nueva).

## Motivación

Sprint 12 dejó `entities[]` vacío a secas en toda memoria episódica: vincularla al grafo hubiera
significado correr extracción de entidades por LLM en el camino síncrono de cada `POST /v1/query`.
La revisión de doc 04 §2 (2026-08-13) resolvió esto reutilizando lo que `graph_sync` ya construye:
si una memoria y un nodo del grafo comparten una fuente (`doc_id`), el nodo ya es relevante para
esa memoria — sin extracción nueva, sin latencia adicional.

## Qué se construye

- **`find_node_ids_by_sources`** (`packages/core/src/kos_core/storage/neo4j.py`): nodos cuyo
  `sources[]` interseca con una lista de `doc_id`. Cypher simple (`any(...) WHERE s IN $doc_ids`),
  sin tocar el esquema existente.
- **`kos.memory_learn`** (`apps/workers/src/kos_workers/tasks/memory.py`) resuelve `entities[]`
  llamando a esa función con las `sources[]` de la memoria, inyectada como `resolve_entities`
  (mismo patrón de dependencia que `embed`, testeable con un stub).
- Tests: unitario (`test_memory_task.py`, resolución fake) e integración real contra Neo4j
  (`test_neo4j_integration.py`, nodos que comparten/no comparten fuente).

## Verificación

Contra infra real (`make up` + worker Celery + API + Ollama nativo, vault ya ingerido: 718
documentos, 2278 nodos): `POST /v1/query` con `"¿qué es Next.js?"` devolvió evidencia de 8
documentos; la memoria episódica resultante (`GET /v1/memory` / `memory_items`) quedó con
`entities[]` de 33 node_ids — todos nodos del grafo que comparten alguna de esas 8 fuentes. 246
tests (236 unitarios + 10 de integración de `packages/core`), ruff y `mypy --strict` (core)
limpios.

## Qué se recorta (deuda visible)

- Si una memoria no comparte ninguna fuente con el grafo (inferida solo de la conversación, sin
  evidencia documental), `entities[]` sigue vacío — aceptado en doc 04 §2, no es un bug.
- `kos.memory_consolidate` no recalcula `entities[]` de la semántica resultante (hereda `[]`,
  igual que antes de este sprint) — las semánticas se arman desde el `content` destilado del
  cluster, no desde `sources[]` fusionadas hacia el grafo. Se deja para si hace falta cuando
  `GET /v1/memory` empiece a usarse para navegar por entidad, no solo por tipo/texto.

## Qué se aprendió

- El patrón de inyección (`embed`/`resolve_entities` como `Callable` async, núcleo testeable
  separado de la task real) sigue pagando: agregar un segundo colaborador externo a
  `_learn_core` no tocó el test existente más que sumarle el nuevo parámetro.
- Verificar en vivo exigió arrancar API + worker manualmente (`make dev` no estaba corriendo) —
  el primer intento con `celery ... --workdir` falló por una opción que no existe en esta versión
  de Celery; el comando correcto es el mismo que ya documenta el Makefile (`dev-workers`), corrido
  desde la raíz del repo sin flags extra.
