# 11 — Recomendador e inteligencia proactiva

**Estado:** 🔵 En revisión, implementado · **Última actualización:** 2026-08-18 · **Habilita:** Fase 5

> **Construcción completa 2026-08-18** (Sprints 22–26): `RecommenderAgent`, dos tipos de
> recomendación (lagunas, contradicciones), feedback loop, UI. El criterio de salida de v1.0 sigue
> en ventana de medición real hasta 2026-09-18 (doc 07) — por eso este doc queda en 🔵 y no 🟢
> todavía: promoverlo a Aprobado espera a que el criterio de salida se confirme cumplido, no solo
> a que el código esté terminado.

## 1. Principio

**El sistema genera valor sin que le hagas preguntas.** Hasta v0.5, todo lo que el sistema produce
es respuesta a una consulta explícita (`/v1/query`) o a una interacción del usuario. El Recomendador
es el primer componente que actúa por iniciativa propia: observa cambios reales en el grafo de
conocimiento y propone algo — sin que nadie se lo haya pedido en ese momento.

**Alcance de v1.0 (decidido 2026-08-16, ver [07 — Roadmap](07-roadmap-versiones.md)):** v1.0 cubre
*solo* el Recomendador. El resto de lo que doc 07 originalmente agrupaba bajo "v1.0" — SDK de
conectores, API pública `/v1` estable, empaquetado reproducible — se movió a v1.1 (Plataforma), sin
diseñar todavía. Empaquetar las cuatro iniciativas en una sola versión repetía, a mayor escala, el
mismo patrón que ya hizo correr v0.3/v0.4/v0.5 al doble de lo estimado.

## 2. Modelo de datos: `Recommendation`

```
Recommendation
├── recommendation_id
├── type                # gap | contradiction | related_relation | roadmap | reorganization
├── title
├── description
├── evidence[]          # EvidenceRef (doc 06 §3) — mismo contrato que ya usa AgentResponse
├── target_entities[]   # node_ids del grafo que motivan la recomendación
├── confidence          # 0–1, mismo significado que en doc 02 §3.1/§4
├── priority             # para ordenar qué mostrar primero
├── status                # pending | accepted | dismissed | expired | superseded
├── dismissed_reason
├── source_event_id       # trazabilidad al graph.updated que la disparó
├── created_at / resolved_at
```

**Decisión: tabla nueva en Postgres (`recommendations`), no un sexto tipo de `MemoryItem`.**
`MemoryType` (doc 04 §2) es un conjunto cerrado de 5 valores pensado para contenido que se
recupera por similitud y **decae** (`salience`, doc 04 §3). Una `Recommendation` tiene un ciclo de
vida distinto — `pending → accepted/dismissed/expired`, sin decaimiento por fórmula — forzarla
dentro de `MemoryItem` mezclaría dos modelos de vida distintos bajo un mismo tipo. Migración
Alembic nueva (mismo mecanismo que `packages/core/alembic`, único dueño del esquema, doc 10 §9),
con índices por `status`, `type` y `created_at` para servir `GET /v1/recommendations?status=&type=`.

## 3. Qué dispara la generación

**Gatillo: `graph.updated`**, decidido explícitamente sobre las otras dos alternativas evaluadas
(job periódico puro, o evento + batch de refuerzo) — el sistema debe reaccionar a cambios reales
del conocimiento, no a un reloj.

### 3.1 Estado real del evento (hallazgo al planificar esta fase, 2026-08-16)

`GraphUpdated` (`packages/core/src/kos_core/schemas/events.py`) documenta en su docstring que es
"emitido por `kos.graph_sync` y por correcciones manuales" — pero **`kos.graph_sync`
(`apps/workers/src/kos_workers/tasks/graph_sync.py`) nunca publica el evento**. Solo las
correcciones manuales de grafo (`PATCH`/`DELETE /v1/graph/*`) lo emiten hoy. La deuda registrada
en `docs/deuda-tecnica.md` ("nadie consume `graph.updated`") es en realidad doble: el camino
automático (sync del vault) tampoco lo **emite**. El Sprint fundacional de esta fase (§ ver doc 08,
Sprint 22) debe resolver ambas partes, no solo agregar un consumidor.

### 3.2 Mecanismo de entrega: Celery encadenado, no pub/sub

`kos:events` (`packages/core/src/kos_core/storage/redis.py`) es un canal pub/sub efímero de
Redis: sin cola, sin consumer group, sin replay. Un `RecommenderAgent` suscripto directo a ese
canal perdería cualquier evento publicado mientras el proceso no está corriendo — inaceptable en
un side-project que no corre 24/7. Este es exactamente el problema que doc 04 §1.1 ya resolvió
para el aprendizaje ("v0.4 implementa 'Learning'/'Memory' como tasks de Celery encadenadas
directamente", no como suscriptor de eventos) — el Recomendador sigue el mismo patrón:

- `kos.graph_sync` encadena un task nuevo, `kos.recommend_from_graph_update`, al terminar una
  sincronización exitosa — mismo estilo de encadenado que `kos.ingest_document` →
  `kos.embed_document` → `kos.enrich_document` → `kos.graph_sync`.
- Las correcciones manuales de grafo (`PATCH`/`DELETE /v1/graph/*`) encadenan el mismo task en vez
  de depender de que algo escuche `kos:events`.
- La **semántica** del evento `GraphUpdated` no cambia — sigue siendo "el grafo cambió, con estos
  `node_ids`/`relation_ids`" y sigue documentado como tal en doc 06 §3 — solo cambia el
  *mecanismo de entrega* dentro del proceso.
- **Debounce:** una resincronización real del vault puede tocar decenas de nodos en segundos. El
  task nuevo agrupa `node_ids` en una ventana corta antes de disparar una pasada del Recomendador,
  en vez de una pasada por nodo individual.

## 4. Qué tipos de recomendación cubre el primer corte

El criterio de v1.0 en doc 07 lista cinco tipos. No todos entran en el primer corte:

| Tipo | v1.0 (primer corte) | Motivo |
|---|---|---|
| Lagunas de conocimiento | **Sí** | `PREREQUISITE_OF`/`KNOWS` ya existen en la ontología (doc 02 §3.2, `KNOWS` ya anotado "deducida por el recomendador") — es una consulta de grafo, no NLP nuevo |
| Contradicciones | **Sí** | `CONTRADICTS` ya reservado en doc 02 §3.2 exactamente para esto ("detección de contradicciones (Fase 5)") — más costoso que lagunas porque requiere comparar afirmaciones, no solo recorrer una relación existente |
| Relaciones descubiertas | No | necesita heurística nueva (similitud de embeddings entre clusters desconectados, o un paso LLM) sin base existente en el grafo actual |
| Roadmaps personalizados | No | depende de que existan lagunas primero — es una vista derivada/secuenciada sobre gaps; natural para una iteración posterior de Fase 5 |
| Reorganización de Obsidian | No | doc 04 §6 ya la dejó para "Fase 5, autonomía configurable"; `obsidian.update_note`/`create_folder` ya existen (deuda cerrada 2026-08-26, doc 06 §4), pero lo pendiente es el flujo de aprobación real para una reorganización autónoma — el ítem de mayor riesgo y alcance |

Los tres tipos diferidos no se prometen en v1.0. Quedan como iteración posterior de la misma Fase 5.

> **Redefinición de "laguna" (Sprint 23, decidido 2026-08-17):** al implementar apareció que
> **nunca se creó ningún nodo que represente al usuario, ni ninguna arista `KNOWS`** — `Person`
> en la ontología (doc 02 §3.1) es un tipo genérico para gente mencionada en las notas (autores,
> colegas), no "vos"; no hay seed ni bootstrap que lo cree. "Laguna = `PREREQUISITE_OF` sin
> `KNOWS`" tal como está escrito arriba no se puede calcular hoy. Redefinición operable adoptada:
> una laguna es un nodo `PREREQUISITE_OF` de algo con `confidence` bajo el umbral de visualización
> ya establecido en doc 02 §4 regla 4 (`< 0.5`) — "poco evidenciado en tu vault" como proxy de
> "posiblemente no lo sabés", sin inventar `KNOWS`/`Person` real. Crear un nodo "vos" + poblar
> `KNOWS` de verdad queda como deuda documentada (`docs/deuda-tecnica.md`) para cuando haya un
> caso de uso concreto (ej. una UI de "marcar como sabido"). Implementado en
> `kos_core.storage.neo4j.gaps_by_prerequisite()`.

> **Precisión de "contradicciones" (Sprint 24, decidido 2026-08-17):** el nodo `Claim` que doc 02
> §6 imagina para esto ("afirmaciones atómicas... para memoria semántica y contradicciones") sigue
> sin existir — diferido a una revisión futura de la ontología, no bloqueó el sprint. A diferencia
> de lagunas (consulta de grafo pura), no hay forma determinística de detectar contradicciones:
> candidatos = chunks de documentos distintos con similitud de embedding en una banda intermedia
> `(0.75, 0.92)` — el techo es el mismo valor que `DUPLICATE_THRESHOLD` (doc 04 §6): por encima de
> eso ya es "duplicado/mismo contenido", no contradicción — más un veredicto final de un LLM sobre
> el texto real de los dos chunks (falla a "no contradice" ante ambigüedad, doc 11 §5 abajo). En
> la verificación en vivo, el modelo local (`llama3.2`) fue conservador y no confirmó
> contradicciones ni en casos obvios — limitación de calidad del modelo, no del mecanismo, deuda
> documentada (`docs/deuda-tecnica.md`). Implementado en
> `kos_core.storage.search.similarity_band_chunks()` +
> `kos_workers.tasks.recommend._default_contradiction_verdict()`.

## 5. Cómo se generan

`RecommenderAgent` nuevo en `packages/agents`, sobre el mismo contrato `AgentRequest`/
`AgentResponse` que el resto de los agentes (doc 03 §2, consistencia y testeabilidad) — pero
**no** entra al catálogo del Planner ni a `Plan.steps`/`Plan.post`: esos existen para resolver una
consulta del usuario, y el Recomendador no responde preguntas. Se invoca directo desde
`kos.recommend_from_graph_update`, mismo patrón que `LearningAgent` (Sprint 21, doc 04 §1.1) vía
servidor MCP embebido en el worker.

**Decisión de alcance: reglas y consultas de grafo determinísticas, no un loop de planificación
LLM.** El primer corte agrega funciones nuevas de recorrido de grafo (ej. `gaps_by_prerequisite`
para lagunas) y calcula gaps/contradicciones así — sin paso LLM todavía (título/descripción
también se arman por template, no redactados). Es más auditable y más barato que un loop de
planificación completo, y evita que un modelo chico (`llama3.2`) decida autónomamente qué
recomendar.

> **Precisión (Sprint 23, 2026-08-17):** `gaps_by_prerequisite` se implementó como función de
> `kos_core.storage.neo4j` (mismo nivel que `most_connected_nodes`), no como plantilla pública de
> `POST /v1/graph/query` (doc 06 §2) como este párrafo insinuaba originalmente — el único
> consumidor real (`RecommenderAgent`/`kos.recommend_from_graph_update`) llama a
> `kos_core.storage.neo4j` directo, mismo patrón que `kos.memory_learn` (Sprint 21). Agregar
> superficie pública nueva sin consumidor HTTP real quedó fuera; se puede promover a plantilla
> pública después si aparece un caso de uso (ej. una UI de debug), sin romper nada.

Esto ajusta la promesa de doc 03 §6 ("Fase 5 | El Recomendador genera planes proactivos sin
consulta del usuario"): "plan" ahí se lee como "acción proactiva", no como un `Plan`/`PlanStep`
generado por el Planner — la generación en sí es determinística en el primer corte.

## 6. Dónde se almacenan

Tabla `recommendations` en PostgreSQL (§2). Sin duplicar el grafo ni la memoria: `target_entities[]`
referencia `node_ids` existentes, `evidence[]` referencia `doc_id`/`chunk_id` existentes — mismo
principio de "nada sin evidencia" que doc 02 regla 3.

## 7. Cómo se exponen

- `GET /v1/recommendations?status=&type=` — ya listado en doc 06 §2 (Fase 5), sin cambios.
- `PATCH /v1/recommendations/{id}` — **nuevo**, falta hoy en doc 06 §2. Body `{status, reason?}`.

**UI:** superficie mínima (badge o lista) dentro de un panel existente de `apps/web`, no un panel
nuevo — el criterio de éxito ("≥1 recomendación útil por semana") no exige una pantalla dedicada.
Se decide el panel concreto al planificar el sprint de UI (doc 08, Sprint 25).

## 8. Feedback loop (aceptar / descartar)

Análogo a la corrección de nodos del grafo (doc 02 regla 5): `PATCH /v1/recommendations/{id}` con
`{status: "accepted" | "dismissed", reason?}`.

- **Aceptar no escribe automáticamente al grafo ni al vault en v1.0.** Evita ampliar el blast
  radius de escrituras autónomas antes de tener uso real que lo justifique — mismo criterio
  conservador que ya aplicó doc 04 §6 a la reorganización de notas ("siempre como propuesta
  aplicable... nunca toca el vault sin aprobación").
- **Descartar** una recomendación debe suprimir su regeneración inmediata para la misma firma
  (`type` + `target_entities`) — necesita una clave de deduplicación, mismo espíritu que la
  detección de duplicados de doc 04 §6.

> **Implementado en Sprint 25 (2026-08-17):** `PATCH /v1/recommendations/{id}` (idempotente contra
> doble-click — solo actúa sobre `pending`, mismo criterio que `archive_memory`). Hallazgo real: el
> guardarraíl de dedup de Sprint 23 (`has_pending_recommendation`) solo miraba `pending` — un
> descarte real dejaba la firma libre para la siguiente pasada. Renombrado a
> `has_active_recommendation`, ahora bloquea también `accepted`/`dismissed`. Superficie mínima:
> `RecommendationsPanel` (`apps/web/src/features/recommendations/`) embebido en `StatusPage`, sin
> pestaña nueva en el nav.

## 9. Relación con `LearningAgent` / `MemoryAgent`

| | `LearningAgent` | `RecommenderAgent` |
|---|---|---|
| Disparo | cada `/v1/query` respondida (post-paso fijo, doc 03 §3) | `graph.updated` (evento de cambio de grafo) |
| Almacén | `MemoryItem` (memoria episódica) | `Recommendation` (tabla nueva) |
| Consumo | recall reactivo (`memory.recall`, elegido por el Planner) | superficie proactiva (`GET /v1/recommendations`) |

Este documento formaliza los dos últimos pasos del pipeline de aprendizaje que doc 04 §4 ya
dibujaba pero dejaba "fuera de v0.4": "Actualizar roadmap" y "Actualizar conocimiento" — ambos
marcados ahí como Fase 5.

## 10. Métricas / criterio de éxito

Traducción operable del criterio de doc 07 para un proyecto de un solo usuario, sin harness de
evaluación grande: una recomendación cuenta como **útil** si se marca `accepted`, o si no se
`dismissed` dentro de los 7 días de creada. Registro manual simple durante la ventana de uso real
(mismo patrón que `docs/eval/` para búsqueda) — no se construye infraestructura de medición nueva
para esto en v1.0.

## 11. Riesgos y no-objetivos

- Sin auto-aplicación de recomendaciones: toda escritura derivada requiere aprobación explícita.
- Sin escritura autónoma al grafo o al vault en v1.0 (§8).
- Los tres tipos diferidos (§4) no se prometen en esta versión.
- SDK de conectores, API pública `/v1` y empaquetado quedan fuera — son v1.1 (doc 07).

## 12. Evolución por fases

| Fase | Estado de esta arquitectura |
|---|---|
| Fase 3 (v0.4) | Memoria y aprendizaje construidos; los dos últimos pasos del pipeline de doc 04 §4 quedan dibujados pero fuera de alcance |
| Fase 4 (v0.5) | Planner/agentes reales; `graph.updated` sigue huérfano (deuda documentada, Sprint 9/21) |
| Fase 5 (v1.0, este doc) | `graph.updated` se emite y se consume de verdad; `RecommenderAgent` genera gaps y contradicciones por reglas/consultas de grafo |
| Fase 5 (iteración posterior) | Relaciones descubiertas, roadmaps personalizados, reorganización de Obsidian |
