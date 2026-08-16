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

## Auditoría de cierre v0.5 (2026-08-16) — hallazgos nuevos, sin sprint asignado

Revisión puntual al cerrar v0.5: tests de integración completos, `pnpm test`/`pnpm lint` de
`apps/web`, y lectura dirigida de las herramientas externas nuevas (Sprint 20). No es una retro de
sprint — es una foto del estado real antes de planificar v0.6.

| Ítem | Riesgo | Origen |
|---|---|---|
| `web.open` (`packages/mcp-tools/.../tools/web.py`) hace `httpx.get(url)` sobre cualquier URL que el Planner (LLM) le pase, sin allowlist/denylist ni bloqueo de rangos privados/loopback/metadata (`169.254.169.254`, `localhost`, `10.0.0.0/8`…) — SSRF clásico si un plan (generado por un LLM que puede ser influenciado por contenido externo vía `web.search`) apunta a un recurso interno | Medio — mitigado hoy por ser local-first de un solo usuario sin red interna sensible detrás de la API, pero se vuelve real si KOS corre en una red con otros servicios internos | Auditoría de cierre de v0.5, no bloqueaba la demo de Sprint 20 |
| `Constraints.timeout_s` (default 30s, presupuesto de todo el plan, doc 03 §3) no tiene relación con el timeout de cada llamada HTTP a Ollama (`_DEFAULT_TIMEOUT = 120.0` en `kos_core/llm/ollama.py`, fijo, no lee `Constraints`) — un solo paso con una llamada a Ollama lenta puede tardar hasta 120s aunque el plan haya pedido un presupuesto de 30s; `executor.py` solo corta *entre* oleadas, nunca cancela una llamada en curso | Medio — ya documentado como limitación de diseño en `executor.py`, pero el desacople concreto de los dos timeouts (30s vs 120s) no estaba escrito en ningún lado | Auditoría de cierre de v0.5 |
| `github.py`/`web.py` (Sprint 20) no tienen retry/backoff ni manejo explícito de rate limit — la API pública de GitHub sin `GITHUB_TOKEN` da 60 req/hora; agotarla tira un 403 que sube como `ToolError` genérico (el executor lo degrada bien, pero sin distinguir "temporalmente sin cuota" de "la tool está rota") | Bajo — no bloquea nada hoy (uso esporádico, un solo usuario), pero sería el primer cuello de botella real si el Research agent se usa seguido | Auditoría de cierre de v0.5 |
| `web.open` no limita el tamaño de la descarga antes de truncar a `_OPEN_MAX_CHARS` — una URL que sirva un archivo grande se descarga entero a memoria antes de cortarse | Bajo — mismo perfil de riesgo que el punto anterior, autoinfligido en un entorno de un solo usuario | Auditoría de cierre de v0.5 |

## Sin sprint asignado todavía

| Ítem | Origen |
|---|---|
| Catálogo de `graph` en el Planner acotado a `query` (`most_connected`/`nodes_by_type`) — `get_node`/`find_path` necesitarían resolver un nombre a `node_id` primero, paso que no existe | [Sprint 18](sprints/sprint-18.md) — no bloqueaba la demo de Sprint 18 |
| `obsidian.read_note`, `obsidian.update_note`, `obsidian.create_folder` (doc 06 §4) siguen sin implementar — solo `create_note` se migró a MCP | [Sprint 20](sprints/sprint-20.md) (addendum) — sin caso de uso real que las pida todavía |
| El catálogo del Planner describe `research`/`memory` en texto libre; con `llama3.2` (modelo chico) el LLM a veces omite campos requeridos en los `inputs` de un paso — el sistema ya degrada correctamente ese caso, pero no hay validación adicional en el prompt para reducir la tasa | [Sprint 20](sprints/sprint-20.md), reafirmado en [Sprint 21](sprints/sprint-21.md) | Ajuste fino, sin sprint asignado |
| Nadie consume el evento `graph.updated` (Learning/Recomendador no existen) | [Sprint 9](sprints/sprint-09.md), decisión explícita de dejarlo fuera de [Sprint 21](sprints/sprint-21.md) | Sin sprint asignado todavía |
| El `trace_id` original de `/v1/query` no se propaga hasta el `LearningAgent` — la task de Celery genera uno nuevo (`uuid4()`) al invocarlo | [Sprint 21](sprints/sprint-21.md) | Ajuste fino de observabilidad, sin sprint asignado |
| Catálogo `memory` del Planner solo cubre `recall` — `MemoryAgent.store` elegido por el LLM (más allá del aprendizaje automático de cada interacción) queda fuera de alcance | [Sprint 21](sprints/sprint-21.md) — alcance explícito, sin caso de uso real todavía |

## UI/UX — baja prioridad, sin sprint asignado

| Ítem | Origen |
|---|---|
| Sin UI de auditoría de memoria en `apps/web` (solo API) | [Sprint 12](sprints/sprint-12.md), reafirmado en [Sprint 15](sprints/sprint-15.md) — decisión explícita del usuario de dejarla fuera del cierre de v0.4 |
| Grafo: sin animación de layout en vivo, sin zoom/pan, sin resaltado de caminos en el canvas | [Sprint 10](sprints/sprint-10.md) |

## Calidad / ajuste fino — sin sprint asignado

| Ítem | Origen |
|---|---|
| 3 fallos de desambiguación léxica en el set de evaluación (36/38 = 94.7%) — errores de ranking, no de datos faltantes | [Sprint 03](sprints/sprint-03.md), [Sprint 05](sprints/sprint-05.md) |
| Clasificación de entidades imprecisa del LLM ligero sin tuning (ej. "Docker" como `Organization`) | [Sprint 06](sprints/sprint-06.md) — mitigada por la corrección manual desde [Sprint 09](sprints/sprint-09.md), pero la causa raíz sigue |
| `SIMILARITY_THRESHOLD` (entity resolution, 0.9) y el umbral de "candidata clara" de `s0` son valores iniciales conservadores, no ajustados con uso real | [Sprint 06](sprints/sprint-06.md), [Sprint 08](sprints/sprint-08.md) |

## Operativa — sin dueño

| Ítem | Origen |
|---|---|
| `test_search_integration.py::test_busqueda_lexica_vectorial_e_hibrida` falla contra el vault real actual | Encontrado en la sesión de Sprints 13-15 (2026-08-15); reproducido también en el commit base, no es una regresión de esos sprints — sin investigar todavía |
| Sin corrección manual de memoria (`locked`, análogo a la corrección de nodos del grafo de Sprint 9) | [Sprint 14](sprints/sprint-14.md) — sin caso de uso real que lo haya pedido todavía |
