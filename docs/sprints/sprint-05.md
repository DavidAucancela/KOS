# Retro — Sprint 5: "Robustez y PDF/Git"

**Cerrado:** 2026-07-17 · **Fase:** 1 (v0.2 — Knowledge Core) · Cierre de v0.2

## Qué se demostró

- **Conector PDF** (`packages/connectors/pdf/`): extrae texto por página con `pypdf`, título desde metadata/outline con fallback al nombre de archivo; el blob binario original (no el texto extraído) sube a MinIO gracias al nuevo campo `RawDocument.raw_bytes` (doc 05 §2, "blob original a MinIO"). OCR queda fuera de alcance hasta Fase 3, como estaba definido.
- **Conector Git** (`packages/connectors/git/`): indexa README(s) y `**/*.md` de un repo ya clonado (nunca código fuente en Fase 1), con metadata del último commit por archivo (`git log` vía subprocess, sin dependencia nueva).
- **Reingesta incremental completa** (doc 05 §5): `kos.sync_source` ahora detecta también los documentos que desaparecieron de `discover()` y los marca tombstone (`documents.deleted_at`, migración 0004) retirando sus chunks — la evidencia deja de citarse sin perder el blob original en MinIO. `list_documents` excluye tombstones por defecto.
- **`kos reindex`** (`scripts/kos_reindex.py`, `make reindex [s=<fuente>]`): reencola una fuente completa con `force=True`, ignorando `content_hash` conocidos — reconstruye los derivados desde MinIO + la fuente, tal como exige doc 09 §backup.
- **Observabilidad real** (`kos_core/observability.py`, doc 09 §6): logs JSON con `trace_id` inyectado por `ContextVar`, trazas OpenTelemetry en la API (un span por request, en el middleware existente), en los workers (un span por task Celery vía signals `task_prerun`/`task_postrun`) y en las llamadas a Ollama (`ollama.embed`/`ollama.generate`, con tokens de prompt/completion como atributos). Exportador de consola síncrono por defecto — sin collector OTLP en el compose todavía; es el punto de extensión cuando lo haya.
- Gate: **119 tests Python** (+2 de observabilidad), ruff + `ruff format --check` + `mypy --strict` en core limpios, `pnpm --filter kos-web lint` limpio (sin cambios en la web este sprint).

## Qué se recortó (deuda visible)

- **Métricas Prometheus** (doc 09 §6, tercera pata de observabilidad junto a logs y trazas): no se tocó `/metrics` en API/workers ni los targets de `infra/prometheus/prometheus.yml`. Sigue con el comentario de Sprint 1 sin resolver.
- **Los 3 fallos del set de evaluación** (`docs/eval/resultados.md`, cerrado el 2026-07-16: 35/38, 92.1%) no se atacaron — son de desambiguación léxica en el ranking híbrido ("zero" en Conditionals vs. Zero Trust; "Supabase" genérico vs. nota de Nunna; sensibilidad a la formulación entre preguntas casi idénticas), no de conectores ni de ingesta, así que quedan fuera del alcance de este sprint.
- Sin watcher de filesystem/webhooks para ningún conector todavía (Obsidian, PDF, Git): la sincronización sigue siendo bajo demanda (`POST /v1/sources/{id}/sync`) o por `kos reindex`, no en tiempo real (<5 min de doc 05 §6 es meta de Fase 3).
- El tombstone no recalcula confianza de nodos del grafo (doc 05 §5) porque Neo4j/entity resolution son Fase 2 — la frase del documento sobre "confianza de los nodos afectados" no aplica todavía.

## Qué se aprendió

- **Docker Desktop se cae por completo bajo carga sostenida** de Ollama + Postgres + Neo4j + Redis + MinIO simultáneos en la máquina del usuario (visto dos veces: durante el set de evaluación el 2026-07-16 y de nuevo encontrado al arrancar este sprint el 2026-07-17). No son solo los contenedores — el daemon mismo deja de responder (`docker info` falla). Se resuelve con `open -a Docker` + `docker compose up -d`; anotado en memoria del proyecto para no perder tiempo diagnosticándolo de nuevo.
- El contrato `RawDocument` necesitaba un único campo nuevo opcional (`raw_bytes`) para que un conector binario (PDF) pudiera separar "lo que sube a MinIO" de "lo que consume el pipeline de texto" sin tocar `bootstrap()` ni ningún otro conector — el patrón de contratos congelados + forks paralelos con fronteras de directorio (Sprint 1) sigue funcionando: los dos conectores se hicieron en paralelo sin conflicto, y el único ajuste de contrato compartido lo señaló el propio fork del PDF en su reporte en vez de tocarlo por su cuenta.
- Elegir `SimpleSpanProcessor` (síncrono) en vez de `BatchSpanProcessor` para el exportador de consola evita una condición de carrera real: el procesador por lotes exporta desde un hilo de fondo que sobrevive al cierre de stdout al terminar los tests, y lanza `ValueError: I/O operation on closed file`.

## Actualización 2026-07-18 — deuda de este sprint resuelta

Dos de los tres puntos de deuda de arriba se atacaron en un follow-up inmediato (los otros dos,
watchers y grafo, siguen correctamente en su fase futura):

- **Métricas Prometheus**: `GET /metrics` en la API, `start_http_server` en los workers
  (puerto `KOS_WORKER_METRICS_PORT`, 9808 por defecto), 5 métricas reales (documentos
  ingeridos/retirados, duración de pipeline, tokens de LLM, duración de requests HTTP) en un
  `CollectorRegistry` propio en `kos_core/observability.py`. Verificado con `make obs-up`: los
  3 targets (`prometheus`, `kos-api`, `kos-workers`) quedan `UP`.
- **Ranking híbrido**: se agregó `title_search` como tercera rama de RRF en
  `packages/core/src/kos_core/storage/search.py`. El primer intento (título vía
  `tsvector`/`to_tsquery`) no sirvió: la config `'simple'` sin stemming hace que "conditional"
  (de la pregunta) y "conditionals" (del título) sean tokens distintos, y `websearch_to_tsquery`
  exige TODAS las palabras de una pregunta natural. Se reemplazó por `word_similarity` de
  `pg_trgm` (ya habilitado en `infra/postgres/init.sql`), que tolera plural/singular y errores de
  tipeo por similitud de trigramas. Resultado contra el set de evaluación real
  (`scripts/run_eval.py`, recreado — el de Sprint 5 era desechable): **36/38 = 94.7%**, sube
  desde 35/38 (92.1%). Arregla el caso de `jonathan.sec`; los otros dos fallos
  (`Zero Conditional`, `Nunna/Supabase`) resultaron ser más difíciles de lo esperado — títulos
  verbosos autogenerados por el LLM (s2/resumen) producen falsos positivos de trigrama contra
  documentos no relacionados, y se documentan como límite conocido de esta heurística en vez de
  seguir persiguiéndolos (ver `docs/eval/resultados.md`).
