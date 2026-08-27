# Deuda técnica — registro vivo

No es un documento de diseño (no está en el índice 00-10 de [docs/README.md](README.md)): es un
registro transversal de lo que cada retro de sprint dejó como deuda, juntado en un solo lugar para
no tener que releer `docs/sprints/*.md` entero cada vez que se planifica un sprint nuevo. Cada
retro sigue siendo la fuente de verdad del detalle — esto solo indexa.

**Cómo se actualiza:** al cerrar un sprint, si su retro (`docs/sprints/sprint-NN.md`, sección "Qué
se recorta"/"Qué queda abierto") deja algo pendiente, se agrega una fila acá. Al resolverse, la
fila se mueve a "Resuelta" con el sprint que la cerró (no se borra: es historial).

## Resuelta

| Ítem | Origen | Resuelto en |
|---|---|---|
| `packages/mcp-tools` sin código (solo README) | [Sprint 9](sprints/sprint-09.md) | [Sprint 16](sprints/sprint-16.md) |
| Import-linter de doc 09 §2 ("se rechaza en CI") mencionado en el doc pero nunca implementado | Hallazgo al planificar Sprint 16 (2026-08-15) | [Sprint 16](sprints/sprint-16.md) |
| `memory_items.sources` con filas viejas (`list[str]`, pre-Sprint 14) rompía `GET /v1/memory` con 500 | Hallazgo al construir `memory.recall` en Sprint 16 (bug heredado de Sprint 14, no de Sprint 16) | [Sprint 16](sprints/sprint-16.md), backfill SQL puntual de 5 filas |
| `tests/__init__.py` en `packages/mcp-tools` y `packages/agents` colisionaban en el mismo nombre de módulo `tests` (ningún otro paquete del repo usa `__init__.py` en `tests/`) — rompía la colección de pytest al correr la suite completa | Introducido por mí mismo en Sprint 16/17, encontrado al agregar `packages/agents` | [Sprint 17](sprints/sprint-17.md), se sacaron ambos `__init__.py` |
| `search_storage.hybrid_search`/`lexical_search` mockeados en tests de `/v1/query` dejaron de interceptar el embedder real tras Sprint 17 (el `MCPAppContext` capturaba `embedding_client` al arrancar el lifespan, antes de que el test lo reemplazara) — la mayoría de los tests pasaban igual porque pegaban contra Ollama real sin que nadie lo notara | Introducido por mí mismo en Sprint 17 al embeber el servidor MCP en `apps/api` | [Sprint 17](sprints/sprint-17.md), tests ahora inyectan el fake antes de que arranque el lifespan |
| `GraphAgent._node_evidence` no completaba `EvidenceRef.quote` — `WritingAgent` armaba citas vacías para evidencia de grafo, el LLM concluía "no hay evidencia" pese a que sí la había | Introducido en Sprint 17 (nunca se notó porque `GraphAgent` era standalone), encontrado al conectarlo al Planner en Sprint 18 | [Sprint 18](sprints/sprint-18.md) |
| Un paso de evidencia que falla (ej. el LLM propuso un `node_type` inválido) tumbaba toda la request de `/v1/query` con 500 en vez de degradar | Hallazgo de Sprint 18, probando el Planner contra infra real | [Sprint 18](sprints/sprint-18.md), el executor ahora degrada pasos de evidencia que fallan (`writing` sigue propagando el suyo) |
| Doc 03 §6 decía que "Fase 2 agregó el paso de grafo al pipeline fijo", pero `/v1/query` nunca incorporó contexto del grafo a sus respuestas — el grafo se construyó (Sprints 6-11) como panel explorable separado en la UI, no como evidencia de respuesta | Hallazgo al planificar Sprint 17 (2026-08-15) | [Sprint 18](sprints/sprint-18.md), el Planner decide cuándo el grafo aporta al plan |
| `Planner` no exigía presupuestos (`Constraints.timeout_s`/`max_steps` se pasaban pero no se hacían cumplir) | [Sprint 18](sprints/sprint-18.md) — alcance explícito, dejado para el sprint que persiste el plan | [Sprint 19](sprints/sprint-19.md) |
| Plan generado no se persistía — `GET /v1/plans/{id}` no existía | [Sprint 18](sprints/sprint-18.md) — alcance explícito | [Sprint 19](sprints/sprint-19.md) |
| Tools MCP que devuelven una lista top-level llegan envueltas en `{"result": [...]}` (distinto de las tools de grafo, que siempre devuelven un objeto con listas anidadas) — `ResearchAgent` iteraba directo sobre el resultado crudo y explotaba con `TypeError` | Hallazgo de Sprint 20, probando `ResearchAgent` contra la API real de GitHub | [Sprint 20](sprints/sprint-20.md), `_unwrap_list()` |
| `obsidian.create_note` implementado directo en la API, no como herramienta MCP (desviación documentada, doc 06 §4) | Sprint 7, doc 06 §4 — pospuesto en Sprint 20, retomado a pedido directo del usuario | [Sprint 20](sprints/sprint-20.md) (addendum, 2026-08-16), `packages/mcp-tools/.../obsidian.py` + `packages/core/src/kos_core/notes.py` |
| Memoria se escribe pero nunca se lee — `/v1/query` no consulta memoria para responder (doc 04 §3 paso "Recuperación" nunca construido) | Hallazgo de la sesión 2026-08-15 (Sprints 13-15), no ligado a una retro puntual anterior | [Sprint 21](sprints/sprint-21.md), `memory` se suma al catálogo del Planner |
| `kos.memory_learn` llamaba `kos_core.memory_learn` directo, no un agente real (doc 04 §1.1 lo prometía desde v0.4) | [Sprint 12](sprints/sprint-12.md), doc 04 §1.1 | [Sprint 21](sprints/sprint-21.md), `LearningAgent` vía MCP embebido en el worker |
| `test_list_tools_expone_las_7_herramientas` (`packages/mcp-tools/tests/test_server_integration.py`) seguía fijado en las 7 tools de Sprint 16 — Sprint 20 sumó 5 tools más (`github.*`, `web.*`, `obsidian.create_note`) sin que nadie actualizara este test; fallaba en silencio porque los tests de integración no corren en el `pytest` por defecto (`-m 'not integration'`) | Auditoría de cierre de v0.5 (2026-08-16), no ligada a una retro puntual — arrastrada desde Sprint 20 sin que ninguna retro la haya notado | Auditoría 2026-08-16, test renombrado y actualizado a las 12 tools reales |
| `web.open` hacía `httpx.get(url)` sobre cualquier URL que el Planner (LLM) le pasara, sin bloquear rangos privados/loopback/metadata — SSRF si un plan apuntaba a un recurso interno | Auditoría de cierre de v0.5 (2026-08-16) | Auditoría 2026-08-16, `_guard_public_url()` (`web.py`): resuelve el hostname y bloquea IPs privadas/loopback/link-local/reservadas/multicast, revalidando cada salto de redirección a mano (`follow_redirects=False` + loop, hasta 5 saltos) |
| `Constraints.timeout_s` (presupuesto del plan) no tenía relación con el timeout fijo de cada llamada HTTP a Ollama (120s) — un paso lento podía tardar hasta 120s pese a un presupuesto menor | Auditoría de cierre de v0.5 (2026-08-16) | Auditoría 2026-08-16: `generate()`/`embed()` (`kos_core/llm/ollama.py`) aceptan `timeout` opcional; `Planner`/`WritingAgent` pasan `request.constraints.timeout_s` en sus llamadas reales a Ollama |
| `github.py`/`web.py` sin retry/backoff ni manejo explícito de rate limit — GitHub sin `GITHUB_TOKEN` da 60 req/hora; agotarla se veía como un `ToolError` genérico | Auditoría de cierre de v0.5 (2026-08-16) | Auditoría 2026-08-16: `_http.get_with_retry()` (reintenta solo fallos de transporte, 2 intentos con backoff corto) + `RateLimitedError` en ambas tools cuando el servidor responde 403/429, con mensaje distinto según haya o no `GITHUB_TOKEN` configurado |
| Nadie consume el evento `graph.updated` (Learning/Recomendador no existen) — y, hallazgo al planificar v1.0 (doc 11 §3.1, 2026-08-16): `kos.graph_sync` tampoco lo *emitía* nunca, pese a que su propio docstring lo prometía; solo las correcciones manuales lo publicaban | [Sprint 9](sprints/sprint-09.md), decisión explícita de dejarlo fuera de [Sprint 21](sprints/sprint-21.md) | [Sprint 22](sprints/sprint-22.md): `kos.graph_sync` encadena `kos.recommend_from_graph_update` (Celery, no pub/sub — doc 11 §3.2); `RecommenderAgent` esqueleto consume el disparo y persiste vía `recommendations.store` |
| `PlanOut.post` es un campo requerido en la API real desde Sprint 21, pero `apps/web/src/api/schema.d.ts` nunca se había regenerado desde entonces — el tipo generado ni siquiera tenía ese campo. `TracesPage.test.tsx` construía un `PlanOut` de prueba sin `post`, y como el tipo viejo no lo exigía, `tsc -b` nunca lo notó. Al regenerar `schema.d.ts` en Sprint 25 (necesario para los tipos de `Recommendation`), `post` apareció de golpe como requerido y `tsc -b` rompió — encontrado y corregido en Sprint 26 al investigar por qué el build fallaba (Sprint 25 lo había atribuido erróneamente a "preexistente", basado en que el diff de `schema.d.ts` no *borraba* líneas — pero agregar un campo requerido nuevo a un tipo existente rompe a los consumidores igual, sin necesitar ninguna eliminación) | Hallazgo real en Sprint 25 (drift entre API real y tipos del frontend, agravado por regenerar `schema.d.ts` por primera vez en mucho tiempo) | [Sprint 26](sprints/sprint-26.md): `plan()` en `TracesPage.test.tsx` ahora incluye `post: []` |
| `RecommendationsPanel` solo mostraba `pending` — sin historial de aceptadas/descartadas en la UI | [Sprint 25](sprints/sprint-25.md) — alcance explícito | Mejora de interfaz (2026-08-18): toggle "Pendientes/Historial" en `RecommendationsPanel`, `useRecommendations` trae todo (`limit=100`, sin filtro de status) y la UI deriva ambas vistas client-side |
| Sin badge de conteo de recomendaciones pendientes en el nav | [Sprint 25](sprints/sprint-25.md) | Mejora de interfaz (2026-08-18): badge en el ícono "Estado" del nav (`App.tsx`), mismo `useRecommendations()` que ya usaba el panel |
| Grafo sin zoom/pan en el canvas | [Sprint 10](sprints/sprint-10.md) | Mejora de interfaz (2026-08-18): zoom (rueda del mouse) y pan (arrastrar el fondo) manuales sobre el `viewBox` del SVG en `GraphCanvas.tsx`, mismo criterio ya usado para el arrastre de nodos desde Sprint 10 (sin traer `d3-zoom`); animación de layout en vivo y resaltado de caminos siguen sin sprint asignado, ver "UI/UX" abajo |
| Grafo real 85% desconectado (2.284 nodos, solo 312 relaciones al diagnosticar, 2026-08-19): `s8_relations.py` solo proponía relaciones intra-documento; resolución de entidades débil y cara (`canonicalize()` sin sinónimos + loop de coseno en memoria sin embeddings persistidos); s7/s8 truncaban a 8000 caracteres en vez de iterar chunks | Hallazgo real verificando la UI del grafo (2026-08-19), diagnosticado en [doc 12](12-calidad-de-extraccion-de-entidades-y-relaciones.md) | PR 1 (#15): resolución de entidades indexada (pgvector + ANN, `node_embeddings`). PR 2 (#16): extracción por chunk, sin truncar. PR 3 (#17): relaciones cross-documento (`kos.discover_cross_document_relations`), más un hallazgo real en el camino: `kos_core.json_utils.strip_code_fence` descartaba en silencio JSON válido del LLM cuando `llama3.2` agregaba prosa después del cierre \`\`\` — corregido, beneficia también al Planner. PR 4 (#18): `scripts/backfill_graph_extraction.py` para reprocesar el grafo existente con el pipeline nuevo |
| `test_search_integration.py::test_busqueda_lexica_vectorial_e_hibrida` fallaba contra el vault real actual — no era una regresión de código: `hybrid_search` (doc 08, Sprint 3) trae candidatos de léxica/vector/título con `limit*2` antes de fusionar con RRF, pero el test comparaba el resultado híbrido contra la unión de listas individuales pedidas con el `limit` original (5, no 10) — un chunk que rankeaba 6º-10º en una señal individual (fuera de ese top-5 más chico) podía ganar un lugar legítimo en el híbrido top-5 vía RRF, y el test lo marcaba como error | Encontrado en la sesión de Sprints 13-15 (2026-08-15); reproducido también en el commit base, no era una regresión de esos sprints — sin investigar hasta ahora | Diagnosticado 2026-08-27 corriendo el test de integración contra el vault real (`make up`, `pytest -m integration`): el universo de comparación del test ahora se pide con el mismo `limit*2` que `hybrid_search` usa de verdad, en vez del `limit` más chico de las aserciones léxica/vectorial por separado |
| Sin métrica de tasa de degradación del Planner por `degraded_reason` agregada en el tiempo (solo por request individual) | Doc 09 §6 nunca se extendió tras Sprint 18-19 | Diseño ad-hoc 2026-08-21: `GET /v1/plans/metrics` agrega `degradation_by_reason` y `degradation_rate` sobre la ventana pedida, con insight determinista (sin LLM) si supera 15% o sube >10pp vs. el período anterior |
| Sin métrica de distribución de agentes elegidos por el LLM agregada en el tiempo | Doc 09 §6 nunca se extendió tras Sprint 20-21 | Diseño ad-hoc 2026-08-21: `GET /v1/plans/metrics` agrega `agent_distribution` (conteo de pasos por agente vía `jsonb_array_elements(steps)`), con insight si un agente concentra >60% de los pasos |
| Chat sin historial persistente (`useState` en memoria, se perdía al refrescar) | Sin origen registrado — hueco identificado al revisar la interfaz | Diseño ad-hoc 2026-08-21: tablas `conversations`/`messages` (migración `0010`), `POST /v1/query` gana `conversation_id` opcional (auto-crea si falta), `GET/DELETE /v1/conversations`, sidebar con agrupación por fecha relativa, búsqueda y archivado en `apps/web/src/features/chat/` |
| Catálogo `memory` del Planner solo cubre `recall` — exponer `store` sin blindarlo permitiría que contenido contaminado en la evidencia recuperada indujera una escritura de memoria sin aprobación humana real (mismo perfil que el SSRF ya mitigado en `web.open`) | [Sprint 21](sprints/sprint-21.md) — alcance explícito, riesgo de seguridad documentado en la revisión de 2026-08-20 | Diseño ad-hoc 2026-08-26 (doc 06 §4 addendum): se expone `agent="memory"`/`operation="store"` al Planner, pero `executor.py` fuerza `confirm=false` incondicional en ese paso — el LLM nunca puede aprobarlo. `memory.store` (único punto de entrada de escritura) persiste el intento rechazado como `MemoryProposal` pendiente (tabla `memory_proposals`, migración `0012`) en vez de perderlo; `GET/PATCH /v1/memory/proposals` + `MemoryProposalsPanel` (`apps/web`) cierran el loop de aprobación humana, mismo patrón que accept/dismiss de `Recommendation` (Sprint 25) |

## Ya resueltas en rama sin mergear (2026-08-20, `sprint-21-learning-agent`)

Trabajo hecho en una sesión de auditoría **sobre `sprint-21-learning-agent` (base v0.5), antes de
que se descubriera que `main` ya tenía v1.0 completo** (Sprints 22-26 mergeados el 2026-08-18) — la
rama nunca se mergeó a `main` y diverge de ella. Los 3 ítems de abajo están resueltos ahí
(commits `473aa26`, `dfa2b91`) pero **siguen pendientes en `main`** hasta que se porten:

| Ítem | Cómo se resolvió en la rama |
|---|---|
| `web.open` no limitaba el tamaño de la descarga antes de truncar | Streaming (`aiter_bytes`) con corte a `_OPEN_MAX_CHARS*2` bytes, sin cargar el archivo completo a memoria |
| `trace_id` original de `/v1/query` no se propagaba hasta el `LearningAgent` | `plan_id` viaja desde `apps/api/routes/query.py` → `memory_service.enqueue_learn` → `kos.memory_learn` (Celery) → `LearningAgent` como `trace_id`, fallback a `uuid4()` |
| Catálogo de `graph` en el Planner acotado a `query` | `find_nodes_by_name()` (Neo4j, case-insensitive) + tool MCP `graph.find_node_by_name` (14ª herramienta si se porta) + `GraphAgent`/catálogo del Planner ampliados a `query`/`find_node_by_name`/`get_node`/`find_path`; `executor.py` deja de forzar `operation="query"` incondicional |

**Antes de portar**: `main` ya sumó `recommendations.store` como 13ª herramienta MCP en paralelo
(Sprint 22) — portar `graph.find_node_by_name` la haría la 14ª, no la 13ª como dice el commit
original. Revisar también si `executor.py`/`planner.py` cambiaron de forma incompatible en el
camino (Sprints 22-26 no tocaron el Planner de `/v1/query`, pero conviene verificar antes de
aplicar el diff a ciegas).

## Sin sprint asignado todavía

| Ítem | Origen |
|---|---|
| `obsidian.read_note`, `obsidian.update_note`, `obsidian.create_folder` (doc 06 §4) siguen sin implementar — solo `create_note` se migró a MCP | [Sprint 20](sprints/sprint-20.md) (addendum) — sin caso de uso real que las pida todavía |

## Monitoreo — sin dueño, próximo frente de trabajo

Doc 09 §6 promete "métricas de negocio desde el inicio", pero la cobertura real quedó parada en lo
que Sprint 5/5-addendum construyó (documentos ingeridos, latencia de pipeline, tamaño del grafo) —
nada de esto se extendió cuando se agregaron el Planner (Sprint 18), los agentes (Sprint 17-21) ni
el Recomendador (Sprint 22-26).

| Ítem | Origen |
|---|---|
| Sin métrica de latencia **por paso de plan** agregada en el tiempo — `GET /v1/plans/metrics` (2026-08-21) agrega latencia por *plan* (`elapsed_ms`) y distribución de agentes por *conteo de pasos*, pero no promedio de `cost.ms` por agente/tipo de paso; no se puede saber en agregado si `research`/`memory` es sistemáticamente el cuello de botella sin abrir planes uno por uno en Trazas | Doc 09 §6 nunca se extendió | Sin sprint asignado — incremento natural sobre `plan_metrics` (`packages/core/.../storage/postgres.py`) |
| `scripts/recommendations_report.py` calcula el ritmo de recomendaciones útiles a demanda (manual), no como métrica expuesta en `/metrics` — la ventana de medición de v1.0 (2026-08-18 → 2026-09-18) depende de correrlo a mano | [Sprint 26](sprints/sprint-26.md) — alcance explícito del cierre de construcción, la automatización queda para después de cerrar el criterio de salida |
| No existe ningún nodo que represente "el usuario" ni ninguna arista `KNOWS` real (doc 02 §3.2) — `gaps_by_prerequisite` usa `confidence` del propio nodo como proxy de "poco evidenciado" en vez de la ausencia de `KNOWS` que el diseño original proponía | [Sprint 23](sprints/sprint-23.md) — decisión explícita al planificar, sin caso de uso real que justifique crear el nodo todavía |
| `gaps_by_prerequisite` recorre el grafo completo en cada pasada, sin acotar por `node_ids`/`relation_ids` del disparo que la debounceó — aceptable para el volumen de un vault de un solo usuario, no diseñado para escala mayor | [Sprint 23](sprints/sprint-23.md) — alcance explícito |
| El veredicto de contradicción (`_default_contradiction_verdict`) con `llama3.2` (modelo chico local) es conservador — no confirmó contradicciones ni en casos obviamente contradictorios durante la verificación en vivo de Sprint 24; consistente con el diseño fail-safe, pero puede tardar en generar la primera recomendación real de este tipo | [Sprint 24](sprints/sprint-24.md) | Ajuste fino (¿modelo más capaz para este paso? ¿prompt distinto?), sin sprint asignado |
| `recent_seed_chunks` no acota por el disparo real (`node_ids`/`relation_ids`) — mismo patrón de deuda que `gaps_by_prerequisite`; además, con pocos chunks recientes puede comparar el mismo par en ambas direcciones (dos llamadas al LLM por un solo par candidato) | [Sprint 24](sprints/sprint-24.md) — alcance explícito |
| Banda de similitud de contradicción (0.75–0.92) sin tuning contra uso real | [Sprint 24](sprints/sprint-24.md) |

## UI/UX — baja prioridad, sin sprint asignado

| Ítem | Origen |
|---|---|
| Sin UI de auditoría de memoria en `apps/web` (solo API) | [Sprint 12](sprints/sprint-12.md), reafirmado en [Sprint 15](sprints/sprint-15.md) — decisión explícita del usuario de dejarla fuera del cierre de v0.4 |
| Grafo: sin animación de layout en vivo, sin resaltado de caminos en el canvas (zoom/pan sí se resolvió, ver "Resuelta") | [Sprint 10](sprints/sprint-10.md) — animación en vivo queda fuera a propósito: choca con la decisión ya tomada en Sprint 10 de que el layout se calcula una sola vez y no compite con el arrastre manual del usuario; resaltado de caminos necesitaría una interacción nueva ("elegir dos nodos") sin caso de uso pedido todavía |

## Calidad / ajuste fino — sin sprint asignado

| Ítem | Origen |
|---|---|
| 3 fallos de desambiguación léxica en el set de evaluación (36/38 = 94.7%) — errores de ranking, no de datos faltantes | [Sprint 03](sprints/sprint-03.md), [Sprint 05](sprints/sprint-05.md) |
| Bandas de similitud de resolución de entidades (`SIMILARITY_CANDIDATE_FLOOR=0.75`, `graph_sync.py`) y de relaciones cross-documento (`CROSS_DOC_SIMILARITY_FLOOR/CEILING=0.75/0.92`, `cross_doc_relations.py`) sin calibrar contra uso real — mismo criterio de deuda que la banda de contradicción (fila de arriba). Hallazgo en vivo verificando el PR 3 (doc 12 §4, 2026-08-19): la mayoría de coincidencias temáticas reales del vault cayeron en 0.6–0.7, por debajo del piso actual — varios pares de chunks genuinamente relacionados no llegan a generar candidato | [doc 12](12-calidad-de-extraccion-de-entidades-y-relaciones.md) §4/§7 |
| `MAX_CHUNKS_PER_RUN = 30` (`cross_doc_relations.py`) — un documento con más chunks que el tope solo procesa los primeros N en la corrida automática (encadenada tras `kos.graph_sync`); el backfill manual (`scripts/backfill_graph_extraction.py`) no tiene este límite | [doc 12](12-calidad-de-extraccion-de-entidades-y-relaciones.md) §4/§7 — mismo criterio de deuda aceptada que `MAX_CONTRADICTION_SEEDS_PER_RUN`/`gaps_by_prerequisite` |
| Clasificación de entidades imprecisa del LLM ligero sin tuning (ej. "Docker" como `Organization`) | [Sprint 06](sprints/sprint-06.md) — mitigada por la corrección manual desde [Sprint 09](sprints/sprint-09.md), pero la causa raíz sigue |
| `SIMILARITY_THRESHOLD` (entity resolution, 0.9) y el umbral de "candidata clara" de `s0` son valores iniciales conservadores, no ajustados con uso real | [Sprint 06](sprints/sprint-06.md), [Sprint 08](sprints/sprint-08.md) |

## Operativa — sin dueño

| Ítem | Origen |
|---|---|
| Sin corrección manual de memoria (`locked`, análogo a la corrección de nodos del grafo de Sprint 9) | [Sprint 14](sprints/sprint-14.md) — sin caso de uso real que lo haya pedido todavía |
