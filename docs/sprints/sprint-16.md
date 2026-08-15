# Retro — Sprint 16: "Las herramientas hablan MCP"

**Estado:** ✅ Cerrado 2026-08-15. Abre v0.5 — Orquestación de agentes (Fase 4), primer sprint
después de cerrar v0.4.

## Motivación

`packages/mcp-tools` llevaba desde Sprint 9 como deuda documentada: un README sin una sola línea
de código, ni siquiera registrado en el workspace de `uv`. ADR-0005 exige que toda herramienta
(interna o externa) se exponga por MCP, pero nada lo hacía. Este sprint construye el primer
servidor real, envolviendo lo que ya existe (grafo, búsqueda, documentos, memoria) antes de tocar
el pipeline fijo de `/v1/query` — ese refactor es Sprint 17.

## Qué se construye

- **`packages/mcp-tools`** (`kos_mcp`), registrado en el workspace de `uv` por primera vez.
  Servidor MCP real (`MCPServer` — el SDK renombró `FastMCP`→`MCPServer` entre lo que se conocía
  del paquete `mcp` y la versión real instalada, `2.0.0`; verificado en vivo contra el SDK real
  antes de escribir código, no asumido) sobre transporte stdio (ADR-0006 local-first).
- **7 herramientas**: `vector.search`, `docs.read_document`, `graph.get_node`, `graph.find_path`,
  `graph.query`, `memory.recall` (lectura) y `memory.store` (escritura, sincrónica in-process —
  decidido con el usuario: devuelve `memory_id` real de inmediato, no encola a Celery).
- **`permissions.py`**: gate sincrónico y real para herramientas de escritura (`WRITE_TOOLS`,
  hoy solo `memory.store`) — sin `confirm=true` no escribe, punto; cada invocación se audita vía
  logging JSON estructurado. Requirió extender `_JsonFormatter` (`kos_core.observability`), que
  hasta ahora ignoraba los campos `extra={...}` de un log — sin eso el logging "estructurado" de
  `permissions.gate` no aparecía en el JSON.
- **4 promociones de lógica de `apps/*` a `packages/core`** (refactor puro, verificado con los
  tests existentes): `evidence_from_hit` (→ `storage/search.py`), el mapeo de grafo completo —
  `NodeWithNeighborhood`/`GraphPathOut`/`GraphQueryRequest`/`GraphQueryResponse`/
  `neighbor_from_record` (→ `schemas/graph.py`), `get_document`/`list_chunks` (→
  `storage/postgres.py`), y `_learn_core` extraído a `kos_core.memory_learn.learn_from_query_answer`.
  Esto no es solo prolijidad: garantiza *por construcción* que `graph.get_node` (MCP) y
  `GET /v1/graph/nodes/{id}` (API) den el mismo resultado — comparten la función, no solo el
  comportamiento — verificado con un test que compara ambos payloads campo a campo contra Neo4j
  real.
- **Import-linter** (decidido con el usuario): `docs 09 §2` decía desde siempre que las reglas de
  dependencia entre `packages/*`/`apps/*` "se rechazan en CI", pero no había ninguna verificación
  real. Se agregó `[tool.importlinter]` (`kos_mcp` no puede importar `kos_api`/`kos_workers`) +
  paso en `ci.yml` — primer caso real donde la regla importaba.

## Verificación

Contra infra real en todo momento, no solo tests: cada una de las 7 herramientas se probó a mano
contra Neo4j/Postgres/Ollama reales antes de escribir sus tests. 19 tests unitarios nuevos (fakes,
mismo estilo que `test_graph_sync_task.py`) + 9 de integración nuevos (Neo4j/Postgres/Ollama
reales) + `scripts/demo_sprint16.py`: servidor real como **subproceso** por stdio (no in-memory,
el camino que usaría un cliente MCP externo de verdad), ejecuta las 7 herramientas de punta a
punta contra infra real, incluyendo el ciclo completo de aprobación de `memory.store` (rechazo sin
`confirm`, escritura real con `confirm=true`, `memory_id` recuperable después vía
`memory.recall`). 283 tests totales (255 unitarios + 28 de integración, excluyendo el roto
preexistente), ruff, `mypy --strict` (core) e import-linter limpios.

## Bug encontrado y arreglado (heredado de Sprint 14, no de este sprint)

Al probar `memory.recall` contra datos reales, `GET /v1/memory` (la API, no solo la tool nueva)
rompía con 500 sobre las memorias escritas *antes* de la migración de esquema de Sprint 14
(`sources` pasó de `list[str]` a `list[SourceRef]`) — 5 filas reales del vault nunca se
backfillearon. Sprint 14 cambió el código para escribir el nuevo formato hacia adelante, pero
nunca migró los datos existentes, y ningún test lo atrapó porque todos usaban datos sintéticos ya
en el formato nuevo. Arreglado con un backfill puntual vía SQL directo (mismo patrón que el
backfill de `doc_type` en Sprint 8 y el de relaciones sin `id` en Sprint 9 — documentado en sus
retros, no una migración Alembic formal):

```sql
UPDATE memory_items
SET sources = (
  SELECT jsonb_agg(jsonb_build_object('doc_id', elem, 'confidence', memory_items.confidence))
  FROM jsonb_array_elements_text(memory_items.sources) AS elem
)
WHERE jsonb_array_length(sources) > 0 AND jsonb_typeof(sources->0) = 'string';
```

5 filas migradas, verificado que `GET /v1/memory` y `memory.recall` funcionan después. De paso,
esto también evitó una rotura latente en `retire_memory_sources`/`kos.memory_consolidate`
(Sprint 14/12), que asumían la misma forma nueva y nunca se habían ejecutado contra estas filas
viejas.

## Qué se recorta (deuda visible)

- `source_confidences[]` (grafo) sigue sin exponerse en ninguna herramienta MCP — decisión de
  Sprint 14, sigue vigente: es un detalle interno del recálculo, no algo que un consumidor
  necesite leer.
- `memory.recall`'s `q` sigue siendo `ILIKE`, no búsqueda semántica (deuda de Sprint 12,
  registrada en `docs/deuda-tecnica.md`, la cierra Sprint 21).
- Cypher de `get_neighborhood` (`storage/neo4j.py`, desde Sprint 9) emite un warning de
  deprecación de Neo4j (`CALL subquery sin variable scope clause`) — inofensivo, no se tocó, es
  ruido en los logs de esta sesión pero no afecta el resultado.
- El Inspector de MCP (`make mcp-inspect`) no se probó de forma interactiva (requiere navegador);
  se validó el mismo camino con un cliente real programático (`scripts/demo_sprint16.py`,
  subproceso stdio) en su lugar.

## Qué se aprendió

- **Verificar el SDK real antes de codear, no confiar en conocimiento previo**: el diseño inicial
  (agente Plan) asumía la API de `mcp` tal como se conocía (`FastMCP`, `mcp.server.fastmcp`) —
  la versión realmente instalada (`2.0.0`) la había renombrado a `MCPServer`
  (`mcp.server.mcpserver`). Correr media docena de scripts sueltos contra el SDK real (nombres de
  tool con punto, cliente in-memory, propagación de excepciones, `structured_content`) antes de
  escribir el código de producción evitó construir sobre supuestos desactualizados — mismo
  criterio que ya había pagado en Sprint 14 con `cypher-shell` antes del Cypher de producción.
- **"Promover antes de envolver" hizo que la demo fuera una garantía, no una aspiración**: decidir
  primero qué lógica movía a `packages/core` (paso 0 del plan) antes de escribir ninguna tool
  convirtió "el mismo resultado que la API" de algo que hay que verificar caso por caso a algo
  imposible de romper por accidente — es la misma función.
- El bug de `memory_items` heredado confirma un patrón que ya se repitió en Sprints 8/9/12/13/14
  de este proyecto: los tests con datos sintéticos frescos no atrapan huecos de migración sobre
  datos reales preexistentes — solo probar contra el vault/datos reales los encuentra.
