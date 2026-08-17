# Retro — Sprint 24: "Contradicciones"

**Estado:** ✅ Cerrado 2026-08-17. Tercer sprint de v1.0 — Recomendador (Fase 5).

## Motivación

Sprint 23 dejó `_async_recommend` extensible por tipo: candidatos → dedup → `RecommenderAgent`
(genérico desde Sprint 22, sin cambios necesarios). Este sprint agrega el segundo tipo real:
contradicciones — el más costoso de los dos planificados en el primer corte de v1.0 (doc 11 §4),
porque no hay forma determinística de saber si dos textos se contradicen.

## Decisiones de alcance (tomadas con el usuario al planificar)

- **Comparación a nivel de chunks (pgvector), no de documentos/resúmenes.** Se evaluaron ambas
  opciones; se eligió la más fiel a "comparar afirmaciones" reales pese al riesgo mayor (doc 08 ya
  avisaba que este sprint podía partirse en dos). `Claim` (el nodo que doc 02 §6 imagina para
  esto) sigue sin existir — diferido a una revisión futura de la ontología, no bloqueó el sprint.
- **Banda de similitud, no un umbral único.** Candidatos = chunks de documentos distintos con
  similitud de embedding en `(0.75, 0.92)` — el techo es literalmente el mismo valor que
  `DUPLICATE_THRESHOLD` (`tasks/memory.py`): por encima de eso ya es terreno de "duplicado/mismo
  contenido" (doc 04 §6), no contradicción.
- **Sin escritura al grafo.** Ni relación `CONTRADICTS` nueva ni el ajuste de `confidence` que
  doc 04 §5 prometía ("contradicción detectada → confidence ↓ en ambas afirmaciones") — ninguno de
  los dos se implementa (doc 11 §11: sin escritura autónoma al grafo en v1.0, mismo criterio que
  lagunas).

## Qué se construye

- **`packages/core/src/kos_core/storage/search.py`**: `similarity_band_chunks()` — mismo estilo
  que `vector_search` (reusa el operador pgvector `<=>`), filtra por `doc_id` distinto y banda de
  similitud.
- **`packages/core/src/kos_core/storage/postgres.py`**: `recent_seed_chunks()` — los `N` chunks
  más recientes con embedding real (vía `Vector` de la columna, no SQL textual, que no
  deserializa el vector de vuelta a Python).
- **`apps/workers/.../tasks/recommend.py`**: `_default_contradiction_verdict()` (LLM, mismo patrón
  DI que `_default_merge_verdict` de entity resolution — Sprint 6 — falla a `(False, "")` ante
  ambigüedad o error de parseo) + `_run_contradiction_recommendations()` (semillas → banda →
  dedup → veredicto → `RecommenderAgent`), corriendo junto a `_run_gap_recommendations` en la
  misma pasada de `_async_recommend`. `OllamaLLMClient` nuevo en este módulo (antes solo usaba
  `OllamaEmbeddingClient`).
- Dedup vía `has_pending_recommendation(type="contradiction", target_entities=[chunk_id_a,
  chunk_id_b] ordenados)` — más preciso que `doc_id` (evita re-verdictar el mismo par de chunks en
  cada pasada, ahorrando llamadas al LLM).
- `EvidenceRef` (ya existente, doc 06 §3) encajó exacto para la evidencia de contradicción —
  `{doc_id, chunk_id, quote, title}` de cada uno de los dos chunks, mejor ajuste que el `node_id`
  que usan las lagunas.

`RecommenderAgent`, `recommendations.store` y `GET /v1/recommendations` no cambiaron — genéricos
desde Sprint 22/23.

## Verificación

Contra infra real (`make up`, sin mocks): se insertaron dos chunks reales en Postgres, en
documentos distintos, con embeddings sintéticos controlados (vectores unitarios en un subespacio
2D — la similitud coseno entre unitarios es `cos(ángulo)`, permite fijar la similitud exacta sin
depender de Ollama) para caer en la banda intermedia, con texto que se contradice de forma obvia
("Redis persiste todo a disco" vs. "Redis nunca persiste nada a disco"). `_async_recommend` real
los encontró como candidatos, llamó al LLM real (Ollama/llama3.2) con el texto real, y el modelo
devolvió JSON válido — pero conservador: `contradicts: false`, incluso repitiendo la prueba con un
caso mucho más obvio ("el cielo es azul" vs. "el cielo nunca es azul"). El mecanismo completo
(candidato → LLM real → parseo real) quedó verificado de punta a punta; el camino "sí
contradice → crea `Recommendation`" se verificó con el LLM mockeado (tests unitarios), ya que el
modelo local no lo disparó en el smoke test.

363 tests unitarios (23 nuevos: veredicto LLM con JSON válido/inválido, `_async_recommend` con
candidato confirmado/no confirmado/sin match/ya pendiente) + 41 de integración (1 nuevo,
`similarity_band_chunks` con banda/techo/piso/exclusión por documento propio — el único fallo es
el preexistente `test_busqueda_lexica_vectorial_e_hibrida`, sin relación con este sprint), ruff,
`mypy --strict` (core) e import-linter limpios.

## Qué se recorta (deuda visible)

- **Precisión del veredicto LLM.** El modelo local (`llama3.2`, chico) es conservador — no
  confirmó contradicciones ni en casos obviamente contradictorios durante la verificación en vivo.
  Es consistente con el diseño (fail-safe a `False`, "más seguro que un falso positivo"), pero
  significa que en la práctica el sistema puede tardar en generar la primera recomendación de este
  tipo, o necesitar un modelo más capaz para este paso específico — ajuste fino, sin sprint
  asignado.
- **Semillas no acotadas por el disparo real** (`node_ids`/`relation_ids` que debounceó) — mismo
  patrón de deuda ya aceptado para `gaps_by_prerequisite` en Sprint 23.
- **Banda de similitud (0.75–0.92) sin tuning contra uso real** — valores iniciales razonados por
  analogía con umbrales existentes, no calibrados con datos reales del vault.
- Con pocos chunks recientes en el vault, `recent_seed_chunks` puede terminar comparando el mismo
  par de chunks en ambas direcciones (A como semilla busca a B, y B como semilla busca a A) — dos
  llamadas al LLM para un solo par candidato. No es incorrecto (el dedup por firma ordenada evita
  crear dos recomendaciones), pero es una llamada al LLM de más; optimizable si el volumen lo
  justifica.

## Qué se aprendió

- Verificar en vivo, no solo con mocks, encontró algo que ningún test unitario podía: el mecanismo
  funciona de punta a punta, pero la calidad del juicio del modelo local es la limitante real, no
  el código. Documentarlo como hallazgo honesto (no forzar un "positivo" artificial ablandando el
  prompt) es más útil para planificar el próximo ajuste que una demo que oculte la limitación.
- Construir embeddings sintéticos controlados (vectores unitarios en un subespacio 2D) para fijar
  la similitud coseno exacta en los tests de integración evitó depender de Ollama real para
  verificar la lógica de la banda — más rápido y determinístico que generar embeddings reales con
  texto elegido a mano y esperar que caigan donde se necesita.
