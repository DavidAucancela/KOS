# Retro — Sprint 17: "Los agentes existen"

**Estado:** ✅ Cerrado 2026-08-15. Continúa v0.5 — Orquestación de agentes (Fase 4).

## Motivación

Sprint 16 construyó el servidor MCP; nadie lo consumía todavía. `apps/api/.../query_service.py`
ya construía un `AgentRequest` para el paso de retrieval, pero lo descartaba sin usarlo
(`_ = retrieval_request  # el contrato de entrada existe para el refactor a Fase 4`) — ese
comentario databa de Fase 1 y este sprint por fin lo cierra. Al planificar se confirmó con el
usuario un alcance conservador: solo Retrieval se conecta al pipeline real de `/v1/query`; Graph y
Memory se construyen como agentes reales y probados, pero standalone — conectarlos ahora con una
heurística casera se tiraría apenas exista el Planner real (Sprint 18), que es quien debe decidir
cuándo hace falta cada uno.

## Qué se construye

- **`packages/agents`** (`kos_agents`), nuevo, solo depende de `core` (doc 09 §2, verificado con
  import-linter): `base.py` (`Agent`/`ToolCaller` como `Protocol`, duck typing — `kos_agents` no
  importa `packages/mcp-tools` ni el SDK `mcp`), `retrieval.py`, `graph.py`, `memory.py`.
- **`RetrievalAgent`** reemplaza `_retrieve()` en `query_service.py`: llama `vector.search` vía
  MCP en vez de `kos_core.storage.search` directo (ADR-0005). Para que no perdiera comportamiento,
  la tool `vector.search` se extendió con `mode` (lexical/vector/hybrid) y degradación a léxica si
  falla el embedder — antes solo hacía hybrid. La orquestación completa (`_retrieve`,
  `_confidence_from_hits`) se promovió a `kos_core.storage.search.retrieve`/`confidence_from_hits`.
- **`GraphAgent`/`MemoryAgent`**: reales, testeados contra infra real, pero standalone — no
  conectados a `/v1/query` (decisión confirmada con el usuario).
- **`kos_mcp` embebible**: `create_server(app_context=None)` acepta un `AppContext` externo — sin
  esto, embeber el servidor en `apps/api` habría abierto un segundo pool de conexiones a
  Postgres/Neo4j solo para que los agentes llamen herramientas. Nuevo `kos_mcp/client.py` con
  `EmbeddedToolCaller` (sesión MCP in-memory, sin subproceso) — `apps/api/main.py` lo arma una vez
  en el lifespan, compartiendo el mismo `postgres_engine`/`neo4j_driver`/`embedding_client` que ya
  usan las rutas REST.
- **`_JsonFormatter`** (`kos_core.observability`) extendido para incluir campos `extra={...}` en
  el JSON de logs — necesario para que `kos_mcp.permissions.gate` audite de verdad (tool_name,
  confirm), no descubierto hasta que se probó el logging estructurado en la práctica (Sprint 16 lo
  daba por hecho sin verificarlo).

## Verificación

Contra infra real en todo momento: `POST /v1/query` real (servidor real, no `TestClient`) sobre
"¿qué es FastAPI?" devolvió 8 evidencias vía `RetrievalAgent`/MCP, respuesta idéntica en forma a
antes del refactor. `GraphAgent`/`MemoryAgent` probados standalone contra el mismo servidor
embebido (`scripts/demo_sprint17.py`): `graph.query` sobre nodos reales, `memory.store` con
aprobación real, `memory.recall` recuperando lo recién escrito. 271 tests unitarios + 30 de
integración (41 nuevos/tocados este sprint), ruff, `mypy --strict` (core) e import-linter limpios.

## Bugs encontrados y arreglados (dos, ambos introducidos en este mismo sprint, no heredados)

1. **Colisión de `tests/__init__.py`**: agregué `__init__.py` en `packages/agents/tests/` (Sprint
   17) sumado al que ya tenía `packages/mcp-tools/tests/` (Sprint 16) — ningún otro paquete del
   repo usa `__init__.py` en su carpeta de tests (todos dependen del modo "rootless" de pytest).
   Con dos carpetas declarándose como el mismo módulo `tests`, la colección de la suite completa
   rompía con `ModuleNotFoundError` en cuanto ambas coexistían. Arreglado sacando ambos
   `__init__.py`, alineado a la convención real del repo — no documentada explícitamente en ningún
   doc, solo observable en el código existente.
2. **Aislamiento de tests roto por captura estática del embedder**: al embeber el servidor MCP en
   `apps/api`, `MCPAppContext.embedding_client` quedó fijado al momento del arranque del lifespan.
   Los tests de `/v1/query` seguían el patrón `client.app.state.embedding_client = fake` *después*
   de crear la app — funcionaba antes porque `routes/query.py` leía `request.app.state` en cada
   request, pero el agente ahora usa la sesión MCP ya armada. La mayoría de los tests seguían
   "pasando" porque terminaban pegándole a Ollama real en vez del fake (sin que nada lo marcara
   como error, salvo el test que necesitaba que el embedder *fallara* de verdad). Arreglado
   moviendo la inyección del fake a un monkeypatch del constructor (`OllamaEmbeddingClient`) antes
   de crear la app, para que el mismo objeto fake llegue tanto a `app.state` como al contexto MCP.

## Qué se recorta (deuda visible)

- `GraphAgent`/`MemoryAgent` siguen sin conectar a `/v1/query` — decisión explícita, ver
  Motivación. Se conectan cuando el Planner (Sprint 18) pueda decidir cuándo corresponde cada uno.
- `AgentResponse.cost` en `RetrievalAgent` mide el tiempo del lado del agente (incluye la llamada
  MCP), no separa cuánto es el embed vs. la búsqueda en sí — suficiente para este sprint, se
  afina si hace falta medir más fino más adelante.
- El servidor MCP embebido en `apps/api` y el standalone (`python -m kos_mcp.server`, Sprint 16)
  ahora son dos caminos de arranque distintos (`create_server()` vs. `create_server(app_context)`)
  — ambos comparten el registro de herramientas, solo difiere el ciclo de vida de las conexiones.

## Qué se aprendió

- El mismo patrón de Sprint 14/16 se repitió: verificar contra infra real (no solo tests con
  fakes) encontró dos bugs reales que los tests con mocks nunca hubieran atrapado — la colisión de
  `__init__.py` solo aparece corriendo la suite *completa* junta, y la fuga del embedder real solo
  se nota si algo depende de que el fake efectivamente falle.
- Definir el `ToolCaller` como `Protocol` (duck typing) en vez de una clase concreta importada
  resolvió limpio la tensión real entre ADR-0005 ("agentes solo hablan MCP") y doc 09 §2
  ("`packages/agents` solo depende de `core`") — sin esa forma, cualquier implementación real del
  llamador de herramientas hubiera forzado a `kos_agents` a importar `kos_mcp`, rompiendo la regla
  de dependencia que el propio import-linter (agregado en Sprint 16) ahora verifica.
