# Retro — Sprint 6: "El grafo empieza a existir"

**Cerrado:** 2026-07-18 · **Fase:** 2 (v0.3 — Knowledge Graph, núcleo) · Primer sprint de v0.3

## Alcance

Solo el núcleo de la integración de Neo4j (decisión explícita con el usuario, dado que Fase 2
completa es v0.3 entero — 5-7 semanas por docs/07): ontología como código, extracción de
entidades/relaciones, entity resolution y escritura real a Neo4j. **Sin API (`/v1/graph/*`) ni
UI todavía** — eso es el siguiente sprint, ya sketcheado en docs/08.

También se atacó, en paralelo, el fix de generación de títulos que venía como deuda del set de
evaluación de Sprint 5.

## Qué se demostró

- **Fix de títulos** (`apps/workers/src/kos_workers/pipeline/s2_metadata.py`): el heading
  capturado como título ahora se limpia de `**negrita**`/`[[wikilinks]]` y se descarta si supera
  80 caracteres (plantillas sin llenar, como la que causaba el falso positivo de
  `Zero Trust (SGT)/Abstract.md` en el eval de Sprint 5). No se re-tituló el vault real todavía —
  eso pide `make reindex`, deuda visible abajo.
- **Ontología como código** (`packages/core/src/kos_core/ontology/`): los 9 tipos de nodo y 10 de
  relación de doc 02 §3, más `canonicalize()` para la deduplicación de doc 05 §4 paso 1.
- **Etapas 7-9 del parser** (`apps/workers/src/kos_workers/pipeline/s7_entities.py`,
  `s8_relations.py`, `s9_confidence.py`): mismo patrón factory que s5/s6 (Sprint 3-4), extracción
  por LLM con salida JSON validada contra la ontología.
- **Entity resolution real** (doc 05 §4, los 5 pasos completos) + escritura a Neo4j
  (`packages/core/src/kos_core/storage/neo4j.py` extendido: `merge_node`, `fetch_nodes_by_type`,
  `merge_relation`), orquestada por la nueva task `kos.graph_sync`
  (`apps/workers/src/kos_workers/tasks/graph_sync.py`), encadenada tras `kos.enrich_document`
  (mismo patrón de encadenado que embed→enrich).
- **Demo real** sobre el `mini_vault` de fixtures (4 notas: FastAPI, Docker, Proyecto KOS, Ideas
  sueltas): **9 nodos y 5 relaciones** reales escritos en Neo4j por el LLM local
  (`llama3.2:latest`), verificado con Cypher a mano en Neo4j Browser. `merge_node` confirmado
  idempotente con Neo4j real (`packages/core/tests/test_neo4j_integration.py`,
  `@pytest.mark.integration`): re-mergear el mismo `canonical_name` actualiza, no duplica.
- Gate: **160 tests** (+35 de este sprint: ontología, s7/s8/s9, graph_sync con fakes, utilidad
  de JSON, integración real de Neo4j), ruff + `ruff format --check` + `mypy --strict` en core
  limpios, `pnpm --filter kos-web lint`/`test` limpios (sin cambios en la web este sprint).

## Qué se recortó (deuda visible)

- **`/v1/graph/*` y correcciones manuales** (doc 06, ya con contrato de superficie definido):
  siguiente sprint, no este.
- **Visualización del grafo en la UI**: siguiente-siguiente sprint (docs/08 lo sketchea después
  de la API).
- **Propagar el tombstone de documentos borrados al grafo** (doc 05 §5): al retirar un documento
  (Sprint 5), su evidencia NO se retira todavía de Neo4j ni se recalcula la confianza de los
  nodos afectados — señalado explícitamente en el plan como fuera de alcance de este sprint para
  no dejarlo a medias.
- **Calidad de la extracción es la de un LLM ligero sin tuning**: en la demo, "Docker" se
  clasificó como `Organization` en vez de `Technology`, y dos menciones del mismo proyecto
  ("KOS" y "Proyecto KOS") no se fusionaron porque su similitud de embeddings quedó por debajo
  del umbral de 0.9 — el umbral es conservador a propósito (mejor no fusionar que fusionar mal),
  pero es una palanca de ajuste real para el sprint de correcciones manuales.
- **El vault real no se re-sincronizó** con el grafo todavía (solo se probó con el mini_vault de
  4 notas) — correr `make reindex` sobre las ~690 notas reales implica ~690 llamadas LLM
  adicionales (extracción + relaciones), a evaluar según recursos antes de hacerlo.

## Qué se aprendió

- **`llama3.2` envuelve el JSON en fences de markdown** (` ```json ... ``` `) aunque el prompt
  pida explícitamente "SOLO JSON" — el primer intento de extracción real devolvió 0 entidades/
  relaciones en silencio (el parser tolerante descartaba todo por `JSONDecodeError`) hasta
  diagnosticar la causa con una llamada manual a Ollama. Se corrigió con un helper compartido
  (`kos_workers/pipeline/_json_utils.py::strip_code_fence`) reutilizado por s7 y s8. Vale la pena
  recordar este patrón para cualquier etapa futura que pida JSON estructurado a un modelo local.
- **`enrich.py` reveló el patrón correcto para LLM en tasks async**: las etapas puras
  (`make_X_stage`) están para tests/composición de pipeline, pero en producción las tasks llaman
  al LLM async directamente reutilizando `build_*_prompt`/`parse_*_response` — replicar ese
  patrón en `graph_sync.py` evitó el error real del primer intento (intentar puentear un
  `generate` async con un factory que espera `generate` síncrono, que revienta con "event loop ya
  corriendo").
- **Los datos de test fixtures pueden ya existir en la BD de desarrollo** de sesiones anteriores:
  al registrar una fuente nueva apuntando al `mini_vault`, `sync_source` no encoló nada porque ya
  existían documentos con esos mismos `source_id` (de pruebas de sprints anteriores) con el mismo
  `content_hash` — hubo que usar `kos reindex --source` (Sprint 5) para forzar el reprocesamiento
  completo. Confirma que `kos reindex` es la herramienta correcta para "quiero que esto se vuelva
  a correr sí o sí", no solo para desastres.
