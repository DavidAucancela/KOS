# Retro — Sprint 12: "La memoria existe"

**Estado:** ✅ Cerrado 2026-08-01. Abre v0.4 — Memoria y aprendizaje (Fase 3), sobre la revisión
de doc 04 del mismo día (§1.1: v0.4 como pipeline fijo, no agentes reales — Fase 4 no existe).

## Motivación

Doc 04 llevaba desde Sprint 0 describiendo memoria (episódica, semántica, consolidación,
decaimiento) sin una sola línea de código. La revisión previa a este sprint resolvió el conflicto
de fases (Learning/Memory Agent → tasks de Celery) y definió lo que faltaba (cadencia de
consolidación, fórmula de decaimiento, umbral de duplicados). Este sprint construye la primera
rebanada real: memoria episódica escrita por consulta, consolidada en semántica, auditable.

## Qué se construye

- **`memory_items`** (Postgres + pgvector, migración 0006): `MemoryItem` (doc 04 §2) con
  `embedding`, `entities[]`, `sources[]`, `confidence`, `salience`, `archived_at` (nunca borrado
  físico, doc 04 §3) y `superseded_by` (versionado por consolidación).
- **`kos.memory_learn`**: encolada desde `POST /v1/query` (`memory_service.enqueue_learn`, mismo
  patrón `send_task` por nombre que `source_service.enqueue_sync` — la API no importa
  `kos_workers`, doc 09 §2) sin bloquear la respuesta al usuario. Escribe una memoria episódica
  por cada pregunta respondida (no por comandos como `/crear-nota`, que son acciones, no
  preguntas). `entities[]` queda vacío — sin entity-linking todavía, deuda visible.
- **`kos.memory_consolidate`** (Celery beat, `KOS_MEMORY_CONSOLIDATION_HOURS`, default 24h):
  agrupamiento greedy determinístico (sin LLM) de episódicas activas por similitud de embedding
  >0.92 (mismo umbral que doc 04 §6, ahora como constante de código); clusters de ≥3 generan una
  memoria semántica y marcan las episódicas `superseded_by` — auditable, no oculto.
- **`effective_salience`** (`kos_core.schemas.memory`): decaimiento exponencial con media vida
  configurable (`KOS_MEMORY_SALIENCE_HALF_LIFE_DAYS`, default 30 días), calculado al leer — sin
  job de fondo que reescriba la tabla entera en cada tick.
- **`GET /v1/memory?type=&q=`** (auditoría, filtro de texto simple vía `ILIKE`, no semántico —
  ver deuda) y **`DELETE /v1/memory/{id}`** (archivado, doc 06 §2, ya documentados desde antes de
  este sprint).

## Verificación

Contra infra real: un `POST /v1/query` real (`"¿qué es KOS?"`) disparó `kos.memory_learn` a
través del worker Celery real, y la memoria episódica resultante apareció en `GET /v1/memory`
con `sources[]` derivado de la evidencia real de la respuesta. La ruta de consolidación (cluster
de 3 episódicas similares → 1 semántica, con protección de `MIN_CLUSTER_SIZE`) está cubierta por
tests con fakes (`test_memory_task.py`) más integración real de storage (`test_postgres_memory.py`:
insert/get/archive/list con filtros/paginación, `list_unconsolidated_episodic`/`mark_superseded`)
— no se verificó en vivo con 3 preguntas reales repetidas porque el Ollama local estaba ocupado
por la sincronización real del vault corriendo en paralelo (mismo tipo de contención de recursos
que ya anota la memoria de entorno del proyecto). 235 tests unitarios + 21 de integración
(paquete completo), ruff y `mypy --strict` (core) limpios.

## Qué se recorta (deuda visible)

- **Sin entity-linking**: `entities[]` siempre vacío. Vincular memorias a nodos del grafo (doc 04
  §2: "node_ids del grafo que menciona") requeriría correr extracción de entidades sobre cada
  consulta — mismo costo de LLM que `graph_sync`, pero en el camino síncrono de cada pregunta.
  Se deja para cuando haya evidencia real de que hace falta, no especulativo.
- **Sin recálculo de confianza al perder una fuente** (doc 04 §5): deuda heredada de Sprint 11,
  aplica igual acá — no hay fórmula definida.
- **`q` es `ILIKE`, no búsqueda semántica**: alcanza para auditar sin sumarle una dependencia del
  embedder a un endpoint de solo lectura. Búsqueda semántica sobre memoria espera a que
  `/v1/query` de verdad la consuma (doc 04 §3 paso 3, todavía no construido — hoy `GET /v1/memory`
  es solo auditoría, memoria no influye ninguna respuesta).
- **Sin refuerzo activo de `salience`**: nadie "usa" memoria todavía para responder, así que no
  hay un punto natural donde reforzarla al recuperarla. Decae; no sube. Se resuelve junto con el
  punto anterior.
- **Sin UI de memoria**: la auditoría es solo API por ahora, consistente con el alcance acordado
  al planear el sprint (demo = API, no pantalla nueva).

## Qué se aprendió

- El truco de "pipeline fijo antes que agentes reales" (ya usado por `/v1/query` desde Sprint 4)
  se generaliza limpio a un dominio nuevo: escribir la doc primero con esa aclaración explícita
  evitó cualquier tentación de construir infraestructura de agentes que este sprint no necesitaba.
- Verificar contra infra real encontró, otra vez, un problema operativo y no de lógica: el
  guardián de ahorro de recursos apaga *todo* `docker compose` (no solo lo que detecta idle), así
  que cualquier pausa larga entre pasos de desarrollo obliga a `make up` de nuevo — y si otro
  proyecto local (`llm-observatory`) toma el puerto 5432 mientras tanto, Postgres arranca sin
  publicar el puerto (`{"5432/tcp": []}`) y hay que `--force-recreate` para que vuelva a bindear.
  Anotado como fricción conocida del entorno, no un bug del proyecto.
- La contención de recursos con Ollama local (ya documentada en la memoria de entorno) volvió a
  aparecer: verificar consolidación con preguntas reales repetidas compite por el mismo Ollama que
  la sincronización real del vault. La cobertura de tests con fakes es lo que permite cerrar el
  sprint igual, sin depender de que la máquina esté libre en el momento exacto de la demo.
