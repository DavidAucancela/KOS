# Retro — Sprint 7: "Sincronización automática + crear notas desde el chat"

**Cerrado:** 2026-07-20 · Fuera del plan original de sprints (pedido directo del usuario entre
sesiones) — se documenta igual con el mismo formato para no perder el hilo del proyecto.

## Qué se demostró

- **Polling automático** (`kos.sync_all_sources`, Celery beat): cada `KOS_SYNC_POLL_SECONDS`
  (300s por defecto) se sincronizan todas las fuentes habilitadas solas, sin llamar nada a mano.
  Barato si no cambió nada (reusa el mecanismo de `content_hash` existente). `make dev` ahora
  levanta también `dev-beat`.
- **Crear notas desde el chat**: comando explícito `/nueva-maquina <nombre>` crea una nota real
  en `Security/HackTheBox/Máquinas/<nombre>.md` a partir de una plantilla de `_Templates/`,
  reutilizando el propio sistema de plantillas Templater del usuario (no una plantilla inventada
  en código). Mecanismo genérico (`packages/core/src/kos_core/templater.py` +
  `apps/api/src/kos_api/services/notes_service.py` + `POST /v1/notes`), no atado a HTB — sirve
  para cualquier plantilla futura en `_Templates/`.
- **Plantilla nueva real**: `_Templates/MaquinaHTB.md`, redactada a partir de la estructura real
  de las notas existentes del usuario (`Meow.md`, `Dancing.md`: Configuración Inicial/Comandos/
  Bandera), no inventada desde cero. `_Templates/_README.md` actualizado con la entrada nueva.
- Gate: **173 tests**, ruff + `ruff format --check` + `mypy --strict` en core limpios.

## Qué se recortó (deuda visible)

- **No es un watcher de filesystem real**: es polling cada 5 minutos, no reacción instantánea al
  guardar. Se eligió a propósito (doc 05 §2 ya lo contempla como alternativa válida) sobre un
  watcher real (`watchdog`/inotify) por mucha menor complejidad — sin debounce, sin proceso
  nuevo, reusa infraestructura de Celery ya existente.
- **`obsidian.create_note` no es una herramienta MCP todavía** — es una versión mínima directa en
  la API. La arquitectura completa (`packages/mcp-tools/`, `permissions.py`, aprobación
  formalizada) sigue siendo Fase 3; desviación anotada explícitamente en doc 06 §4.
- **Solo un comando** (`/nueva-maquina`), no un mecanismo genérico de comandos multi-plantilla en
  el chat — el `notes_service` ya está listo para agregar más comandos rápido cuando haga falta
  (YAGNI: no se construyó antes de necesitarlo).
- **`KOS_GRAPH_SYNC_ENABLED` sigue apagado** desde la recuperación del vault real (ver incidente
  abajo) — falta decidir cuándo correr `kos.graph_sync` sobre las ~680 notas reales.

## Incidente y aprendizaje del sprint

**Se rompió la búsqueda del vault real por un bug de Sprint 5, ya arreglado.**
`_known_hashes`/`_retire_missing`/`retire_documents` (tombstone) filtraban solo por `connector`
("obsidian"), no por `source_uuid`. Al correr `kos reindex` sobre una fuente de prueba pequeña
(usada para verificar Sprint 6), el sistema comparó su `discover()` contra TODOS los documentos
"obsidian" conocidos —incluyendo los de la fuente real del usuario, mucho más grande— y marcó
como borrados (tombstone) los ~686 documentos reales, retirándoles los chunks/embeddings de la
búsqueda. **Arreglado de raíz** (source_uuid como filtro adicional en las tres funciones, test de
regresión con Postgres real en `packages/core/tests/test_postgres_retire_documents.py`) y
**recuperado** con `kos reindex --source vault-real` (2432/2432 chunks re-embebidos, confirmado
con una consulta real). De paso se agregó `KOS_GRAPH_SYNC_ENABLED` para poder apagar la etapa de
grafo en reingestas masivas sin duplicar la carga de LLM cuando solo hace falta recuperar la
búsqueda.

**Lección**: nunca registrar/sincronizar una fuente de prueba compartiendo conector con una
fuente real sin verificar primero el alcance de cualquier lógica de "detectar borrados" — y en
general, confirmar con qué fuente exacta se corre `kos reindex --source X` antes de lanzarlo.

## Qué se aprendió (aparte del incidente)

- El vault del usuario ya tenía un sistema de plantillas real (Templater) — mucho mejor
  reutilizar eso que inventar una plantilla nueva escondida en código Python. El mecanismo de
  renderizado quedó genérico por diseño gracias a este hallazgo, no por anticipación.
- Un comando explícito tecleado por el usuario (`/nueva-maquina X`) es una forma simple y
  suficiente de satisfacer la regla de "aprobación" de doc 06 §4 sin construir un flujo de
  confirmación aparte — la propia acción deliberada del usuario ya es la aprobación.
