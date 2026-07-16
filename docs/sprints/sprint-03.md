# Retro — Sprint 3: "Encuentra lo que sé"

**Cerrado:** 2026-07-14 · **Fase:** 1 (v0.2 — Knowledge Core)

## Qué se demostró

- **Embeddings por lotes** (etapa 4, doc 05 §3): task `kos.embed_document` idempotente (solo chunks con `embedding IS NULL`, lotes de 16 con bge-m3) encolada automáticamente tras cada ingesta — una nota nueva en el vault termina embebida en pgvector sin intervención manual.
- **Búsqueda híbrida** sobre el mini-vault, en vivo por `POST /v1/search`:
  - léxica (`websearch_to_tsquery` sobre columna generada tsvector + GIN, migración 0003): "contenedores" → chunk de Docker;
  - vectorial (coseno pgvector): "¿qué base de datos guarda las relaciones del grafo?" → nota Neo4j primera (score 0.63) — recuperación semántica real, sin coincidencia léxica;
  - híbrida (fusión RRF k=60, determinista): la frase parafraseada devuelve el chunk exacto en primer lugar.
- Cada hit lleva la evidencia mínima `{doc_id, chunk_id, quote}` (doc 06 §2) lista para el `/v1/query` del Sprint 4; Ollama caído degrada hybrid→léxica con `degraded: true`.
- Gate completo: **84 tests unit + 2 de integración** (embedding real y búsqueda contra la BD), mypy estricto en core, ruff limpio.

## Qué se recortó (deuda visible)

- **Set de evaluación (30–50 preguntas del vault con respuesta esperada)**: bloqueado hasta tener `OBSIDIAN_VAULT_PATH` apuntando al vault real del usuario. Es el criterio de calidad del sprint (recall@k) y condición para cerrar v0.2 — primera tarea al retomar.
- Config de tsvector `simple` (vault multilingüe): sin stemming es/en; evaluar `spanish` + fallback trgm cuando exista el set de evaluación.
- La búsqueda no filtra por fuente/conector (`?source=`) — llegará con el explorador de la UI (Sprint 4).

## Qué se aprendió

- pgvector con SQL textual requiere `CAST(:param AS vector)` explícito; con el ORM lo resuelve el tipo de columna.
- `RowMapping` de SQLAlchemy no satisface `Mapping[str, Any]` bajo mypy strict; las firmas de fusión aceptan `Mapping[Any, Any]`.
- El patrón de dos agentes paralelos con frontera core+api / workers volvió a integrarse sin conflictos; el único cruce (encolar embed desde ingest) estaba asignado explícitamente a uno solo.
