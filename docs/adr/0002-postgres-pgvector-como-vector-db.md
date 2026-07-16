# ADR-0002 — PostgreSQL + pgvector como base vectorial

**Estado:** Aceptado
**Fecha:** 2026-07-11

## Contexto

El Knowledge Core necesita búsqueda semántica sobre chunks (embeddings) y búsqueda léxica (texto), además de almacenamiento transaccional de documentos, chunks, jobs y memoria. La escala objetivo de v0.x–v1.0 es de miles a cientos de miles de chunks, en una sola máquina.

## Decisión

PostgreSQL con la extensión **pgvector** es el almacén de documentos parseados, chunks, embeddings y memoria. La búsqueda híbrida se hace dentro de Postgres (tsvector/pg_trgm + pgvector, fusión RRF).

## Alternativas consideradas

- **Qdrant / Weaviate / Milvus** — mejores a escala de decenas de millones de vectores, pero añaden un servicio más, otra fuente de verdad y sincronización extra. Innecesario a nuestra escala. Descartadas por ahora.
- **SQLite + sqlite-vec** — atractivo por simplicidad, pero débil para workers concurrentes (Celery) y sin camino claro a multiusuario. Descartada.
- **Elasticsearch/OpenSearch para la parte léxica** — potente, pero pesado; Postgres cubre la necesidad. Descartada.

## Consecuencias

- Positivas: una sola base transaccional para documentos + vectores + memoria; joins entre metadata y similitud; backups triviales; menos servicios que operar.
- Negativas: a >10M de vectores o alta concurrencia de búsqueda habría que reevaluar (índices HNSW de pgvector escalan bien, pero no infinito).
- La interfaz de búsqueda vive en `packages/core`; migrar a un vector DB dedicado sería reemplazar una implementación, no rediseñar.
