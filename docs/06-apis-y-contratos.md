# 06 — Especificación de APIs y contratos entre servicios

**Estado:** 🟢 Aprobado (2026-07-14) · **Última actualización:** 2026-08-16

## 1. Principios

1. **Contratos primero.** Todo cruce de frontera entre dominios usa esquemas Pydantic versionados que viven en `packages/core` — la única dependencia compartida por api, workers y agentes.
2. **La UI solo conoce la API HTTP.** Nunca las bases de datos ni los workers.
3. **Comunicación interna por eventos** (Redis/Celery) para todo lo asíncrono; llamadas directas solo dentro del mismo proceso.
4. **Versionado explícito**: la API pública lleva `/v1/`; los eventos llevan `schema_version`.

## 2. API pública (FastAPI) — superficie v0.1 → v0.4

Solo se especifica aquí la superficie; el detalle de cada esquema se genera como OpenAPI desde el código y se revisa en PR.

### Conocimiento y búsqueda

| Método | Ruta | Descripción | Fase |
|---|---|---|---|
| `POST` | `/v1/query` | Consulta principal: pregunta → respuesta con citas + plan | 1 |
| `POST` | `/v1/search` | Búsqueda híbrida cruda (sin síntesis LLM) | 1 |
| `GET` | `/v1/documents` / `/v1/documents/{id}` | Listado y detalle de documentos ingeridos | 1 |
| `GET` | `/v1/documents/{id}/chunks` | Chunks y evidencia de un documento | 1 |

### Grafo

| Método | Ruta | Descripción | Fase |
|---|---|---|---|
| `GET` | `/v1/graph/nodes/{id}` | Nodo + vecindario inmediato | 2 |
| `POST` | `/v1/graph/query` | Consulta estructurada (plantillas seguras sobre Cypher) | 2 |
| `GET` | `/v1/graph/path?from=&to=` | Camino entre dos entidades | 2 |
| `PATCH` | `/v1/graph/nodes/{id}` | Corrección manual (fija `extracted_by: user`) | 2 |
| `PATCH` | `/v1/graph/relations/{id}` | Corrección manual de una relación (Sprint 9, mismo mecanismo de `locked` que un nodo) | 2 |
| `DELETE` | `/v1/graph/relations/{id}` | Rechaza una relación (Sprint 9): soft delete vía `rejected: true`, el sync no la recrea | 2 |

`POST /v1/graph/query` no acepta Cypher libre: el body es `{template, params}` sobre un set cerrado
de plantillas (Sprint 9): `nodes_by_type` (listado paginado por tipo), `neighbors_by_type`
(vecinos de un nodo, opcionalmente filtrados por tipo de relación/nodo vecino), `most_connected`
(nodos con más relaciones, para priorizar qué revisar a mano), `subgraph` (Sprint 10: los mismos
nodos que `most_connected` más las relaciones activas *entre ellos* — subgrafo inducido, no su
vecindario completo — para dibujar el grafo en la UI sin traer nodos fuera del conjunto mostrado).
Ampliar el set de plantillas es un cambio de código revisado en PR, no una superficie abierta a
query arbitraria.

### Ingesta

| Método | Ruta | Descripción | Fase |
|---|---|---|---|
| `GET/POST` | `/v1/sources` | Listar/registrar fuentes (vault, carpeta PDFs, repo) | 1 |
| `POST` | `/v1/sources/{id}/sync` | Forzar sincronización | 1 |
| `GET` | `/v1/ingest/jobs/{id}` | Estado de un trabajo de ingesta | 1 |

### Memoria, recomendaciones y planes

| Método | Ruta | Descripción | Fase |
|---|---|---|---|
| `GET` | `/v1/memory?type=&q=` | Explorar memoria (auditoría) | 3 |
| `DELETE` | `/v1/memory/{id}` | Olvidar (archivado, no borrado físico) | 3 |
| `GET` | `/v1/plans/{id}` | Traza completa de un plan ejecutado | 4 |
| `GET` | `/v1/plans` | Lista paginada de planes recientes (sin `steps`/`post`) | 4 |
| `GET` | `/v1/plans/metrics` | Métricas agregadas del Planner en el tiempo (latencia por plan y por agente, degradación, distribución de agentes, tokens, insights) | 4 |
| `GET` | `/v1/conversations` | Historial de conversaciones (más recientes primero) | 4 |
| `GET` | `/v1/conversations/{id}` | Detalle + mensajes de una conversación | 4 |
| `DELETE` | `/v1/conversations/{id}` | Archivar una conversación (no borra) | 4 |
| `GET` | `/v1/recommendations` | Lagunas, contradicciones, sugerencias | 5 |
| `PATCH` | `/v1/recommendations/{id}` | Aceptar/descartar una recomendación (doc 11 §8) | 5 |

### Convenciones HTTP

- Errores: RFC 9457 (`application/problem+json`).
- Paginación por cursor (`?cursor=&limit=`).
- Respuestas de consulta siempre incluyen `evidence[]`: lista de `{doc_id, chunk_id, quote, doc_type}` — **una respuesta sin evidencia es un bug**, no una respuesta. `doc_type` (`"content" | "template"`, ver doc 02 §2) permite a la UI y al propio prompt del LLM distinguir una plantilla real de una nota de contenido, evitando que se combinen como si fueran la misma cosa.
- Auth: token local simple en v0.x; OAuth/workspaces en Fase 6.

## 3. Contratos internos (packages/core)

### Datos (definidos en [02 — Modelo de dominio](02-modelo-de-dominio-y-ontologia.md))

`RawDocument`, `ParsedDocument`, `Chunk`, `EntityCandidate`, `RelationCandidate`, `MemoryItem`.

### Agentes (definidos en [03 — Agentes](03-arquitectura-de-agentes.md))

```python
class AgentRequest(BaseModel):
    task: str
    inputs: dict
    constraints: Constraints          # timeout, max_tokens, budget
    trace_id: str

class AgentResponse(BaseModel):
    outputs: dict
    evidence: list[EvidenceRef]       # doc/chunk/node/memory ids
    confidence: float
    cost: Cost                        # tokens, ms
    trace_id: str
```

`EvidenceRef` incluye `doc_type: str | None` (propagado desde `ParsedDocument.doc_type`, doc 02 §2) para que cualquier consumidor sepa si la evidencia citada es una plantilla o una nota de contenido.

Estos contratos se usan desde la Fase 1 (aunque el "planner" sea un pipeline fijo), para que la extracción a agentes reales en Fase 4 sea un refactor y no una reescritura.

### Eventos (bus Redis)

| Evento | Emisor | Consumidores | Payload clave |
|---|---|---|---|
| `document.ingested` | Ingesta | Parser | `source_ref`, `content_hash` |
| `document.parsed` | Parser | Grafo, Aprendizaje | `doc_id`, `pipeline_version` |
| `document.deleted` | Ingesta | Grafo, Aprendizaje | `doc_id` |
| `graph.updated` | Entity Resolution | Aprendizaje, Recomendador | `node_ids[]`, `edge_ids[]` |

> **Entrega real (doc 11 §3, planificado Sprint 22):** `graph.updated` no se entrega vía
> suscripción al canal pub/sub `kos:events` — un consumidor que se suscribiera directo perdería
> eventos publicados mientras no está corriendo. Se entrega vía tasks de Celery encadenados
> (`kos.graph_sync` → `kos.recommend_from_graph_update`), mismo patrón que doc 04 §1.1 ya usa para
> aprendizaje. La semántica del evento no cambia, solo el mecanismo de entrega.
| `conversation.completed` | API | Learning Agent | `conversation_id` |
| `memory.written` | Learning Agent | Recomendador | `memory_id`, `type` |

Todos los eventos llevan `event_id` (dedupe), `schema_version`, `occurred_at` y `trace_id`.

## 4. Herramientas MCP

Toda capacidad con efectos u acceso a datos se expone como herramienta MCP ([ADR-0005](adr/0005-mcp-como-protocolo-de-herramientas.md)). Convención de nombres: `<dominio>.<verbo>_<objeto>`.

| Herramienta | Tipo | Fase |
|---|---|---|
| `vector.search` | lectura | 1 |
| `docs.read_document`, `docs.read_pdf` | lectura | 1 |
| `graph.query`, `graph.get_node`, `graph.find_path` | lectura | 2 |
| `memory.recall`, `memory.store` | lectura/escritura | 3 |
| `obsidian.read_note`, `obsidian.create_note`, `obsidian.update_note`, `obsidian.create_folder` | escritura (requiere aprobación) | 3 |
| `github.search_repos`, `github.search_commits` | lectura externa | 4 |
| `web.search`, `web.open` | lectura externa | 4 |
| `recommendations.store` | escritura (requiere aprobación) | 5 |
| `roadmap.create`, `roadmap.update` | escritura | 5 |

> `recommendations.store` (Sprint 22, v1.0): el `RecommenderAgent` la llama con `confirm=true`
> forzado por código (mismo patrón que `LearningAgent`/`memory.store` — el sistema completando un
> paso ya decidido, no un LLM eligiendo escribir por su cuenta), con dedup por firma
> `type + target_entities` antes de persistir. 13ª herramienta real del servidor MCP.
>
> `roadmap.create`/`roadmap.update` no se construyen en los Sprints 22-26 (v1.0) — "roadmaps
> personalizados" queda diferido a una iteración posterior de Fase 5 (doc 11 §4).

Reglas: las herramientas de escritura requieren aprobación del usuario por defecto; toda invocación se registra con `trace_id` del plan que la causó.

> **Desviación documentada (2026-07-20)**: se implementó una versión mínima de
> `obsidian.create_note` **directamente en la API** (`POST /v1/notes` +
> comando `/nueva-maquina <nombre>` en el chat, ver
> `apps/api/src/kos_api/services/notes_service.py`), no como herramienta MCP.
> La regla de "aprobación del usuario" se satisface porque es el propio
> usuario quien teclea el comando explícito — no hay ningún agente/LLM
> decidiendo escribir de forma autónoma. La implementación completa vía MCP +
> `permissions.py` sigue pendiente para la Fase 3 real; cuando llegue, esta
> ruta se migra o convive con ella. **Planificado para Sprint 20** (doc 08,
> v0.5), una vez que `packages/mcp-tools`/`permissions.py` existan de verdad
> (Sprint 16) — ver también [docs/deuda-tecnica.md](deuda-tecnica.md).
>
> **Actualización (Sprint 8)**: el comando se generaliza de `/nueva-maquina <nombre>`
> (template y carpeta fijos en código) a `/crear-nota <template>|<folder>|<título>`,
> que acepta cualquier plantilla existente en `_Templates/` sin tocar código.
> `/nueva-maquina` se mantiene como alias de compatibilidad (reescribe internamente
> a los mismos parámetros fijos de HTB). Se mantiene la misma regla de aprobación:
> el usuario teclea el comando exacto, típicamente copiado de una respuesta previa
> del sistema (ver "detección de intención de plantilla" más abajo).
>
> **Decisión de alcance (Sprint 20, 2026-08-16)**: la migración de
> `obsidian.create_note` a herramienta MCP real sigue pendiente — decisión
> explícita del usuario al planificar este sprint, para no mezclar "conectar
> el mundo exterior" con "reescribir un camino que ya funciona". Sprint 20 se
> queda con las 4 herramientas externas de la tabla de arriba
> (`github.search_repos`, `github.search_commits`, `web.search`, `web.open`),
> todas de **lectura** — no le suman superficie nueva a `permissions.py`
> (`WRITE_TOOLS` no cambia este sprint). Sin sprint asignado todavía para la
> migración de `obsidian.create_note`; ver `docs/deuda-tecnica.md`.
>
> **Proveedores externos (Sprint 20)**: `github.*` usa la API pública de
> GitHub (sin token para uso liviano; `GITHUB_TOKEN` opcional en `.env` para
> más cuota — doc 09 §5). `web.*` usa la Brave Search API vía
> `BRAVE_SEARCH_API_KEY` (`.env`, sin default: si falta, `web.search`/
> `web.open` devuelven un error claro en vez de fallar silenciosamente).
> Mismo principio de ADR-0006 (cloud opt-in por tarea): estas llamadas salen
> a internet solo cuando el plan decide usar `research`, nunca como parte de
> la ingesta o del pipeline de embeddings.
>
> **Migración a MCP real (2026-08-16)**: `obsidian.create_note` ya existe como herramienta MCP
> real (`packages/mcp-tools/src/kos_mcp/tools/obsidian.py`), con `confirm=true` requerido y gate
> real en `permissions.py` (`WRITE_TOOLS` ahora incluye `"obsidian.create_note"`, mismo patrón que
> `memory.store`). La lógica de renderizado/escritura (antes solo en
> `apps/api/.../notes_service.py`) se promovió a `packages/core/src/kos_core/notes.py` — `kos_mcp`
> no puede depender de `apps/api` (import-linter). Convive con la ruta directa de la API: el
> comando `/crear-nota` del chat sigue llamando la lógica promovida directo (su propia aprobación
> ya la satisface el usuario tecleando el comando, como documenta la nota de Sprint 7 más arriba);
> la tool MCP es la vía que un agente (`WritingAgent`, doc 03 §2: "crea/modifica notas") podrá usar
> más adelante, pasando siempre por el gate de aprobación explícita.
>
> **`read_note`/`update_note`/`create_folder` (2026-08-26, deuda cerrada)**: implementadas con el
> mismo patrón que `create_note` (`kos_core.notes` + wrapper en
> `packages/mcp-tools/.../obsidian.py` + gate real). Las tres entran a `WRITE_TOOLS` (exigen
> `confirm=true`). `update_note` es overwrite total y **nunca crea** — la nota debe existir (crear
> es `create_note`). `kos_core.notes._resolve_in_vault` rechaza rutas que escapan del vault
> (`..`/symlink/ruta absoluta), mismo criterio de no confianza que el guard de SSRF de
> `web.open`. El `WritingAgent` gana los métodos `read_note`/`update_note`/`create_folder`
> (forzando `confirm=true` por código, patrón `LearningAgent`), pero las tools **no** están en el
> catálogo del Planner de `/v1/query` — el LLM no elige `confirm` (regla 7 de CLAUDE.md, mismo
> tratamiento que `memory.store`). Quedan listas para un flujo de aprobación explícito futuro.
>
> Además, `POST /v1/query` gana un paso `s0` (dentro del pipeline fijo, no un
> planner nuevo — ver regla 3 de CLAUDE.md) que detecta con una heurística
> determinista (palabras clave, sin LLM) cuando la pregunta del usuario implica
> "quiero crear algo, ¿qué plantilla uso?". En ese caso el pipeline normal de
> retrieval→síntesis LLM se salta por completo: si existe una plantilla clara en
> `doc_type="template"`, se responde con una cita real y el comando `/crear-nota`
> ya armado; si es ambiguo, se responde con una pregunta de aclaración fija
> (lista de plantillas existentes) en vez de dejar que el LLM sintetice una
> plantilla combinando fragmentos de documentos distintos y no relacionados —
> el motivo original de este cambio (ver retro `docs/sprints/sprint-08.md`).
>
> **Historial de conversaciones + métricas del Planner (2026-08-21, diseño ad-hoc post-cierre
> v1.0, ver `docs/deuda-tecnica.md` "Monitoreo")**: `POST /v1/query` gana `conversation_id`
> opcional en el body — si se omite, se crea una conversación nueva y su id vuelve en
> `QueryResponse.conversation_id` (siempre presente). Cada turno (pregunta + respuesta, con
> `evidence[]` incluida) se persiste en `conversations`/`messages`; esto realiza el evento
> `conversation.completed` ya listado en la tabla de eventos (§3) — planificado desde Fase 1 pero
> nunca implementado hasta ahora. Un fallo al guardar el historial nunca bloquea la respuesta ya
> calculada (mismo principio que ya aplica `insert_plan`). `GET /v1/plans/metrics` no invoca al
> LLM ni al Planner — los "insights" que devuelve son reglas deterministas sobre agregados SQL
> (comparación contra el período anterior), no texto generado; no aplica ni viola la regla 3 de
> CLAUDE.md porque ningún LLM participa.
>
> **Latencia por agente en `/v1/plans/metrics` (2026-08-27, `docs/deuda-tecnica.md` "Monitoreo")**:
> `agent_distribution` agregaba pasos por agente (conteo), pero no si un agente en particular
> (típicamente `research`/`memory`, que hacen I/O real) es sistemáticamente el cuello de botella —
> había que abrir planes uno por uno en Trazas para saberlo. `agent_latency` agrega el promedio de
> `cost.ms` por agente sobre la misma ventana, vía `jsonb_array_elements(steps)` (mismo criterio que
> `agent_distribution`); `count` ahí es la cantidad de pasos con `cost.ms` presente, no el total de
> pasos del agente — un paso degradado (`executor.py`, ver doc 03 §3 regla de degradación) no
> siempre trae `cost`. Sin insight nuevo asociado: los umbrales existentes (`_LATENCY_WARNING_DELTA_PCT`,
> etc.) ya son valores iniciales sin calibrar contra uso real (doc `deuda-tecnica.md` "Calidad /
> ajuste fino") — inventar otro umbral sobre latencia por agente sin datos reales sería la misma
> deuda de nuevo, no una que se cierra.

## 5. Qué congela este documento

Lo estable (cambiar requiere PR sobre este doc + posible ADR): los principios de la sección 1, los contratos de agentes, la lista y semántica de eventos, y la regla de evidencia obligatoria. Lo flexible (evoluciona en el código con revisión normal): campos concretos de los esquemas y rutas adicionales de la API.
