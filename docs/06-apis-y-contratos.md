# 06 — Especificación de APIs y contratos entre servicios

**Estado:** 🟢 Aprobado (2026-07-14) · **Última actualización:** 2026-07-14

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
| `GET` | `/v1/recommendations` | Lagunas, contradicciones, sugerencias | 5 |

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
| `roadmap.create`, `roadmap.update` | escritura | 5 |

Reglas: las herramientas de escritura requieren aprobación del usuario por defecto; toda invocación se registra con `trace_id` del plan que la causó.

> **Desviación documentada (2026-07-20)**: se implementó una versión mínima de
> `obsidian.create_note` **directamente en la API** (`POST /v1/notes` +
> comando `/nueva-maquina <nombre>` en el chat, ver
> `apps/api/src/kos_api/services/notes_service.py`), no como herramienta MCP.
> La regla de "aprobación del usuario" se satisface porque es el propio
> usuario quien teclea el comando explícito — no hay ningún agente/LLM
> decidiendo escribir de forma autónoma. La implementación completa vía MCP +
> `permissions.py` sigue pendiente para la Fase 3 real; cuando llegue, esta
> ruta se migra o convive con ella.
>
> **Actualización (Sprint 8)**: el comando se generaliza de `/nueva-maquina <nombre>`
> (template y carpeta fijos en código) a `/crear-nota <template>|<folder>|<título>`,
> que acepta cualquier plantilla existente en `_Templates/` sin tocar código.
> `/nueva-maquina` se mantiene como alias de compatibilidad (reescribe internamente
> a los mismos parámetros fijos de HTB). Se mantiene la misma regla de aprobación:
> el usuario teclea el comando exacto, típicamente copiado de una respuesta previa
> del sistema (ver "detección de intención de plantilla" más abajo).
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

## 5. Qué congela este documento

Lo estable (cambiar requiere PR sobre este doc + posible ADR): los principios de la sección 1, los contratos de agentes, la lista y semántica de eventos, y la regla de evidencia obligatoria. Lo flexible (evoluciona en el código con revisión normal): campos concretos de los esquemas y rutas adicionales de la API.
