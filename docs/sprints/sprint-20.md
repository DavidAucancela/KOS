# Retro — Sprint 20: "El mundo entra"

**Estado:** ✅ Cerrado 2026-08-16. Continúa v0.5 — Orquestación de agentes (Fase 4).

## Motivación

Todos los agentes hasta Sprint 19 operan solo sobre lo que el usuario ya escribió (vault, grafo,
memoria). Pero doc 03 §2 define un quinto agente, `Research`, desde el principio: "busca fuera
del sistema (web, GitHub, artículos)". Este sprint lo construye real y lo conecta al Planner —
la primera vez que un plan puede salir a internet.

## Decisiones de alcance (tomadas con el usuario al planificar)

- **Fuentes**: GitHub (API pública) y web (Brave Search API) — las dos externas ya listadas en
  doc 06 §4, no una tercera nueva.
- **`obsidian.create_note` sigue sin migrar a MCP real**: la otra mitad del objetivo original de
  este sprint (doc 08, "`permissions.py` real para escritura") se pospuso a pedido explícito del
  usuario, para no mezclar "conectar el mundo exterior" con "reescribir un camino que ya
  funciona sin bloquear nada". Sigue como deuda sin sprint asignado (`docs/deuda-tecnica.md`).

## Qué se construye

- **`packages/mcp-tools/src/kos_mcp/tools/github.py`** (nuevo): `github.search_repos`,
  `github.search_commits` contra la API pública de GitHub. `GITHUB_TOKEN` opcional (`.env`) solo
  para subir la cuota (60→5000 req/hora), nunca requerido.
- **`packages/mcp-tools/src/kos_mcp/tools/web.py`** (nuevo): `web.search` (Brave Search API,
  `BRAVE_SEARCH_API_KEY` requerida — sin ella lanza `MissingApiKeyError` con mensaje claro, no
  devuelve una lista vacía que un LLM leería como "sin resultados") y `web.open` (fetch + extrae
  texto plano con un stripper de tags por regex, sin sumar una dependencia de parsing HTML nueva
  al repo — truncado a 5000 caracteres).
- **`packages/agents/src/kos_agents/research.py`** (nuevo): `ResearchAgent`, mismo contrato
  `Agent` que Retrieval/Graph/Writing. Un `operation` en `inputs`
  (`github_repos`/`github_commits`/`web_search`/`web_open`) decide qué tool MCP invocar.
- **`Planner`**: `research` se suma al catálogo (doc 03 §3) y a `_ALLOWED_AGENTS`;
  `research_agent` es un parámetro opcional del constructor (compatibilidad — un plan que igual
  pida `research` sin el agente registrado simplemente no resuelve ese paso, mismo comportamiento
  que cualquier `agent` fuera del registry).
- **`apps/api/.../routes/query.py`**: `ResearchAgent(caller)` conectado al `Planner` real de
  `/v1/query`.
- **`.env.example`**, `Settings.github_token`/`Settings.brave_search_api_key`: nuevas variables.
- Docs actualizados **antes** del código (CLAUDE.md, "docs antes que código"): doc 03 §3
  (catálogo ampliado), doc 06 §4 (proveedores elegidos, alcance pospuesto documentado), doc 08
  (objetivo/demo de este sprint).

## Verificación

Contra infra e internet reales, sin mocks de red: `scripts/demo_sprint20.py`, 4 escenarios.

1. `github_repos` contra la API real de GitHub (sin token): 3 repos reales devueltos
   (`fastapi/fastapi`, 101k+ estrellas).
2. `web_open` contra `https://fastapi.tiangolo.com` real: texto extraído y truncado.
3. `web_search` sin `BRAVE_SEARCH_API_KEY` (no configurada en este entorno): falla con
   `ToolError` claro al llamar el agente standalone — comportamiento esperado y documentado, no
   un bug (es `executor.py`, Sprint 18, quien degrada un paso de evidencia que falla dentro de un
   plan; el agente standalone no oculta el error).
4. `POST /v1/query` real con una pregunta que pide contexto externo ("¿cuál es el repositorio de
   GitHub más popular sobre FastAPI y qué dice su README?"): el Planner (llama3.2 local) generó
   un plan con un paso `research` real — la elección de usar `research` fue del LLM, no de una
   heurística casera. El plan degradó (`degraded=true`) porque el LLM omitió `operation` en los
   `inputs` del paso `research`; `executor.py` capturó el `ValueError` resultante y degradó ese
   paso a evidencia vacía sin romper la respuesta — el sistema completo (`ResearchAgent` nuevo +
   `executor.py` de Sprint 18) se comportó como diseñado en el primer intento, sin necesitar un
   fix dedicado.

309 tests unitarios (25 nuevos: `test_research_agent.py`, `test_github_tools.py`,
`test_web_tools.py`, más 2 en `test_planner.py`), ruff, `mypy --strict` (core) e import-linter
limpios.

## Bug encontrado y arreglado (uno, solo visible contra infra real)

- **Tools MCP que devuelven una lista top-level llegan envueltas en `{"result": [...]}`**: a
  diferencia de `GraphAgent`, cuyas tools siempre devuelven un objeto con listas anidadas
  (`NodeWithNeighborhood`, `GraphQueryResponse`), `github.search_repos`/`github.search_commits`/
  `web.search` devuelven `list[...]` en el top-level — el SDK MCP envuelve cualquier retorno que
  no sea un objeto en `{"result": ...}` dentro de `structured_content`. `ResearchAgent` iteraba
  directamente sobre el resultado crudo (`TypeError: string indices must be integers`) hasta
  correr `demo_sprint20.py` contra la API real de GitHub. Ningún test con `ToolCaller` fake lo
  hubiera atrapado si el fake no replicaba exactamente esa forma — arreglado con
  `_unwrap_list()` y los fakes de `test_research_agent.py` corregidos para reflejar la forma
  real. Mismo patrón que se repite en este proyecto desde Sprint 8: los bugs reales aparecen al
  cruzar un límite de protocolo real, no en la lógica que ya se prueba con fakes.

## Qué se recorta (deuda visible)

- `obsidian.create_note` sigue sin migrar a herramienta MCP real — decisión explícita del
  usuario, sin sprint asignado todavía.
- El catálogo del Planner describe `research` en texto libre para el LLM (mismo estilo que
  `retrieval`/`graph`); con `llama3.2` (modelo chico) el LLM a veces omite `operation` en los
  `inputs` del paso `research` — el sistema ya degrada correctamente ese caso (ver arriba), pero
  no hay validación adicional en el prompt para reducir la tasa de este error. No bloquea la
  demo: es exactamente el comportamiento "mejor algo que nada" que el diseño de Sprint 18 ya
  contempla.

## Qué se aprendió

- El diseño de degradación de `executor.py` (Sprint 18: un paso de evidencia que falla no tumba
  el plan) ya cubrió, sin cambios, un caso que nunca se probó explícitamente contra él (un
  `ValueError` de un agente completamente nuevo por un input mal formado del LLM) — la señal más
  fuerte de que separar "qué degrada" de "qué propaga" fue la decisión de diseño correcta en
  Sprint 18, no una que solo sirvió para el bug que la motivó.
- Otra vez (Sprint 8/9/12/13/14/16/17/18/20): el bug real de este sprint solo apareció al cruzar
  el límite real del protocolo MCP contra infra real (GitHub), no en la lógica de mapeo que ya
  tenía tests con fakes — los fakes reprodujeron la forma incorrecta hasta que la ejecución real
  la corrigió.
