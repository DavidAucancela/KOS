# Retro — Sprint 4: "Responde con citas"

**Cerrado:** 2026-07-14 · **Fase:** 1 (v0.2 — Knowledge Core) · Caso de uso canónico #1

## Qué se demostró

- **`POST /v1/query` en vivo sobre el mini-vault**: pregunta → retrieval híbrido → síntesis LLM → respuesta con `evidence[]`. "¿Qué es KOS y qué papel juega Obsidian?" se responde citando `[1]` la nota Proyecto KOS, con `{doc_id, chunk_id, quote}` por cita y la traza del plan (`s1:retrieval → s2:writing`).
- **No-alucinación** (doc 06 §2): sin evidencia, la respuesta lo declara y NO se llama al LLM; `evidence=[]`, `confidence=0.0`.
- **Contratos de agentes** `AgentRequest/Response` + `EvidenceRef` en `kos_core.schemas.agents`: el pipeline fijo de 2 pasos ya los usa, de modo que el planner real de la Fase 4 sea un refactor (doc 03 §6).
- **Etapas 5-6 del parser** end-to-end: `kos.enrich_document` genera resúmenes fieles (s5, LLM) y keywords fusionando frontmatter + términos frecuentes (s6), encadenada tras el embedding.
- **UI chat + visor de citas**: los marcadores `[n]` del answer son clicables y abren la cita; el visor carga el documento y resalta el chunk citado. Cliente OpenAPI regenerado incluyendo `/v1/query`.
- Errores precisos: solo el fallo del LLM de síntesis da 503; un fallo de retrieval/BD sube a 500 RFC 9457.
- Gate: **102 tests Python + 7 web**, mypy estricto en core, ruff limpio.

## Qué se recortó (deuda visible)

- **Set de evaluación (30-50 preguntas, >90% con ≥1 cita correcta)**: sigue bloqueado por `OBSIDIAN_VAULT_PATH` del vault real. Es el criterio de cierre de v0.2.
- **Modelo LLM: bajado de qwen3:14b a llama3.2 (~2 GB)** por consumo de recursos de la máquina del usuario. El 3B sintetiza peor (a veces se niega a responder con evidencia válida); `qwen2.5:latest` (4.7 GB) es el punto medio recomendado cuando haya recursos. La calidad de síntesis se medirá con el set de evaluación.
- La heurística de `confidence` (score máx. de retrieval) es provisional; los scores RRF son pequeños (~0.016) y no calibran bien — revisar con el set de evaluación.
- El visor de citas solo se muestra en viewport `lg+` (sin drawer móvil).
- Aún sin auth por token local (doc 06 §1): todo abierto en localhost.

## Qué se aprendió

- El modelo local pesado (14B) satura una máquina de desarrollo: cargar en frío disparaba timeouts (503) en la primera consulta. Default cambiado a un modelo ligero; el tamaño del LLM es una palanca de configuración de primera clase (`OLLAMA_LLM_MODEL`).
- Con cuatro agentes en paralelo sobre fronteras `core+api / api / workers / web` y contratos congelados de antemano, la integración fue de nuevo un refactor menor (un solo ajuste: precisar el 503 de síntesis).
