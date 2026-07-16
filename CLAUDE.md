# KOS — Knowledge Operating System

Motor de conocimiento independiente de fuentes; Obsidian es solo un conector. El proyecto se gestiona como una startup: **docs antes que código** — ninguna fase se implementa sin su documento de diseño aprobado.

## Dónde está todo

- `docs/README.md` — índice de los 10 documentos de arquitectura y su estado (🟡 borrador / 🔵 revisión / 🟢 aprobado).
- `docs/adr/` — decisiones registradas. Cambiar una decisión estructural = nuevo ADR, nunca editar el aceptado.
- `docs/08-plan-de-sprints.md` — qué se construye y en qué orden. Estamos en **Fase 0 / Sprint 0**.
- `apps/` y `packages/` — aún sin código (llega en Sprint 1); cada directorio tiene un README con su responsabilidad.

## Reglas del proyecto

1. El núcleo no conoce ninguna fuente concreta (ADR-0001); nada de lógica especial de Obsidian fuera de su conector.
2. Todo cruce de fronteras usa esquemas de `packages/core`; nada de dicts sueltos.
3. El LLM nunca accede a datos directamente; siempre media el planner (o el pipeline fijo pre-Fase 4).
4. Respuestas de consulta sin `evidence[]` = bug.
5. Local-first: Ollama por defecto; cloud solo opt-in por tarea (ADR-0006).
6. Idioma de los docs: español. Código e identificadores: inglés.

## Comandos

- `make up` / `make down` — infraestructura local (Postgres+pgvector, Neo4j, Redis, MinIO, Ollama).
- `make pull-models` — descarga bge-m3 y el LLM local.
- `make clean` — ⚠️ borra los datos locales (volúmenes Docker de Postgres/Neo4j/Redis/MinIO).
