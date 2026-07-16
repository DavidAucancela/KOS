# Retro — Sprint 2: "El vault entra"

**Cerrado:** 2026-07-14 · **Fase:** 1 (v0.2 — Knowledge Core)

## Qué se demostró

- Vault de prueba (mini-vault de 4 notas con frontmatter, wikilinks, tags y subcarpetas) ingerido completo vía API: `POST /v1/sources` → `POST /v1/sources/{id}/sync` → workers Celery → Postgres/MinIO.
- `GET /v1/documents`, `GET /v1/documents/{id}` y `GET /v1/documents/{id}/chunks` navegables con paginación por cursor; chunks con heading, offsets reales (`body[start:end]` verificado) y flag de embedding.
- Metadata extraída correctamente: título (frontmatter > primer encabezado > filename), autor, fechas, idioma (heurística es/en), tags→keywords, wikilinks→links.
- **Idempotencia** (doc 05 §5): un segundo sync no re-procesa nada (skip por `content_hash`) y no duplica filas.
- Blobs originales inmutables en MinIO bajo `connector/doc_id/content_hash`.
- Eventos `document.ingested` y `document.parsed` publicados en el bus Redis (`kos:events`) con `event_id`/`schema_version`.
- 66 tests Python (conector 24, pipeline 27, resto api/core/workers) + mypy estricto en core.

## Qué se recortó (deuda visible)

- `watch()` del conector Obsidian devuelve vacío (el watcher/polling llega con la reingesta incremental, Sprint 5).
- `GET /v1/ingest/jobs/{id}` sigue pendiente (el sync devuelve `job_id` pero no hay endpoint de estado).
- Las rutas `/v1/sources` y `/v1/documents` no tienen tests unitarios propios (las cubre el e2e manual); añadirlos con el harness de tests de integración.
- `document.deleted` (tombstones) sin implementar — Sprint 5.

## Qué se aprendió

- El frontmatter YAML produce `datetime.date` y los campos JSONB necesitan volcado JSON-safe (pydantic `model_dump(mode="json")`) antes de persistir.
- **Los bind mounts de datos bajo ~/Documents (iCloud) corrompen servicios con estado**: MinIO devolvía 500 (`resource deadlock avoided`). El compose migró a volúmenes nombrados de Docker; backups documentados en doc 09 §8.
- Repartir el sprint entre agentes paralelos (conector / pipeline / wiring) funcionó bien gracias a contratos congelados de antemano en `kos_core.schemas` — los tres flujos se integraron sin fricción.
