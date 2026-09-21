# KOS — Knowledge Operating System

Motor de conocimiento independiente de fuentes; Obsidian es solo un conector. El proyecto se gestiona como una startup: **docs antes que código** — ninguna fase se implementa sin su documento de diseño aprobado.

## Estado actual

**v1.0 construcción completa** (2026-08-18, Sprints 22–26): `RecommenderAgent` se dispara ante
`graph.updated` real (sync automático o corrección manual) y detecta lagunas de conocimiento y
contradicciones, con feedback loop (`PATCH /v1/recommendations/{id}`) y deduplicación por firma.
**El criterio de salida (≥1 recomendación útil/semana) se midió el 2026-09-19 y NO se cumplió**
(21 recomendaciones, todas `gap`, ninguna revisada; 2 de 5 semanas con alguna — doc 07). v1.0 sigue
abierta: no declararla cerrada hasta decidir si se extiende la ventana o se corrige la definición de
"útil" (hoy pasiva: una recomendación que nadie abre cuenta como útil a los 7 días). Código terminado
no es lo mismo que versión cerrada (ver doc 07, regla del roadmap).

Se construye sobre **v0.5 — Orquestación de agentes** (cerrado 2026-08-16): Planner real (LLM
genera planes dinámicos), 6 agentes (Retrieval/Graph/Research/Memory/Writing/Learning) sobre 16
herramientas MCP reales, planes auditables (`GET /v1/plans/{id}`).

**Próximo paso**: no hay sprint numerado en curso. Orden vigente desde 2026-09-19: **monitoreo**
(las métricas del Planner/agentes/Recomendador ya están en `/metrics`, doc 09 §6, incluida cada
pasada del Recomendador — `kos_recommender_runs`; faltan alertas y dashboard de Grafana) y
**Railway fase D** (doc 14: migrar los datos locales — la infra real de la fase C está viva y
verificada desde 2026-09-19, pero Supabase tiene 0 documentos y `sources` vacío, así que el cron
drena una cola vacía). **Diferidos a propósito**: el diseño de UI de
doc 13 §8–§11 y el backfill del grafo. Siguen abiertos en `docs/deuda-tecnica.md` la deuda técnica
y las mejoras de calidad (desambiguación léxica, clasificación de entidades, umbrales sin tuning,
y ahora el ruido de las lagunas). v1.1 (Plataforma) no se planifica hasta cerrar el criterio de
salida de v1.0.

## Dónde está todo

- `docs/README.md` — índice de los 11 documentos de arquitectura y su estado (🟡 borrador / 🔵 revisión / 🟢 aprobado).
- `docs/adr/` — decisiones registradas. Cambiar una decisión estructural = nuevo ADR, nunca editar el aceptado.
- `docs/08-plan-de-sprints.md` — qué se construyó y en qué orden, Sprint 0 → 26 (v0.1 → v1.0). v1.1 sin planificar todavía.
- `docs/deuda-tecnica.md` — registro vivo de deuda técnica; es el punto de partida para cualquier trabajo que no sea un sprint nuevo.
- `apps/` (`api`, `web`, `workers`) y `packages/` (`core`, `connectors`, `agents`, `mcp-tools`) — código real y activo; cada directorio tiene un README con su responsabilidad.

## Reglas del proyecto

1. El núcleo no conoce ninguna fuente concreta (ADR-0001); nada de lógica especial de Obsidian fuera de su conector.
2. Todo cruce de fronteras usa esquemas de `packages/core`; nada de dicts sueltos.
3. El LLM nunca accede a datos directamente; siempre media el Planner real (`packages/agents`, desde Sprint 18).
4. Respuestas de consulta sin `evidence[]` = bug.
5. Local-first: Ollama por defecto; cloud solo opt-in por tarea (ADR-0006).
6. Idioma de los docs: español. Código e identificadores: inglés.
7. Las herramientas de escritura (`WRITE_TOOLS` en `permissions.py`: `memory.store`, `recommendations.store`, `obsidian.create_note`/`read_note`/`update_note`/`create_folder`) requieren `confirm=true` vía el gate real de `permissions.py` — nunca un bypass. El Planner (LLM) nunca decide `confirm=true` por su cuenta en un paso de `/v1/query`, y por eso las tools `obsidian.*` no están en su catálogo (solo `WritingAgent` las expone, forzando `confirm=true` por código); ver el ítem `memory.store` en `docs/deuda-tecnica.md` para el razonamiento completo.

## Comandos

- `make up` / `make down` — infraestructura local (Postgres+pgvector, Neo4j, Redis, MinIO, Ollama).
- `make pull-models` — descarga bge-m3 y el LLM local.
- `make dev` — API + workers + beat + web + vigía de ahorro de recursos.
- `make clean` — ⚠️ borra los datos locales (volúmenes Docker de Postgres/Neo4j/Redis/MinIO).
- Entorno local (macOS/iCloud): exportar `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/kos` antes de invocar `uv` a mano — ver doc 09 §1 si aparece `ModuleNotFoundError` intermitente de `kos_core`/`kos_api`/`kos_workers`/`kos_agents`.
