# KOS — Knowledge Operating System

Motor de conocimiento independiente de fuentes; Obsidian es solo un conector. El proyecto se gestiona como una startup: **docs antes que código** — ninguna fase se implementa sin su documento de diseño aprobado.

## Estado actual

**v1.0 construcción completa** (2026-08-18, Sprints 22–26): `RecommenderAgent` se dispara ante
`graph.updated` real (sync automático o corrección manual) y detecta lagunas de conocimiento y
contradicciones, con feedback loop (`PATCH /v1/recommendations/{id}`) y deduplicación por firma.
**El criterio de salida (≥1 recomendación útil/semana) está en ventana de medición real hasta
2026-09-18** — no declarar v1.0 cerrado hasta verificarlo con `scripts/recommendations_report.py`,
código terminado no es lo mismo que versión cerrada (ver doc 07, regla del roadmap).

Se construye sobre **v0.5 — Orquestación de agentes** (cerrado 2026-08-16): Planner real (LLM
genera planes dinámicos), 6 agentes (Retrieval/Graph/Research/Memory/Writing/Learning) sobre 13
herramientas MCP reales, planes auditables (`GET /v1/plans/{id}`).

**Próximo paso**: no hay sprint numerado en curso. Tres frentes en paralelo sobre
`docs/deuda-tecnica.md` — deuda técnica pendiente (evaluando riesgo real antes de cerrar cada
ítem, no todo lo que parece deuda debe resolverse a ciegas), mejoras de calidad (desambiguación
léxica, clasificación de entidades, umbrales sin tuning), y monitoreo (sin métricas del
Planner/agentes/Recomendador todavía — ver doc 09 §6). v1.1 (Plataforma) no se planifica hasta
cerrar el criterio de salida de v1.0.

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
