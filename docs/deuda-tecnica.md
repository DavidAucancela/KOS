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

## Resuelta por v0.5 (Sprints 18-21), no requiere sprint aparte

| Ítem | Origen | Se resuelve en |
|---|---|---|
| Nadie consume el evento `graph.updated` (Learning/Recomendador no existen) | [Sprint 9](sprints/sprint-09.md) | Sprint 21 (Learning agent) |
| `obsidian.create_note` implementado directo en la API, no como herramienta MCP (desviación documentada, doc 06 §4) | Sprint 7, doc 06 §4 | Sprint 20 |
| Memoria se escribe pero nunca se lee — `/v1/query` no consulta memoria para responder (doc 04 §3 paso "Recuperación" nunca construido) | Hallazgo de la sesión 2026-08-15 (Sprints 13-15), no ligado a una retro puntual anterior | Sprint 21 (Memory agent lee, no solo escribe) |
| Doc 03 §6 dice que "Fase 2 agregó el paso de grafo al pipeline fijo", pero `/v1/query` nunca incorporó contexto del grafo a sus respuestas — el grafo se construyó (Sprints 6-11) como panel explorable separado en la UI, no como evidencia de respuesta | Hallazgo al planificar Sprint 17 (2026-08-15) | `GraphAgent` ya existe y funciona (Sprint 17), pero decidir CUÁNDO una consulta necesita grafo es del Planner — Sprint 18 lo conecta a `/v1/query` |

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
