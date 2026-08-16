# Retro — Sprint 18: "El planner decide"

**Estado:** ✅ Cerrado 2026-08-15. Continúa v0.5 — Orquestación de agentes (Fase 4).

## Motivación

Sprint 17 dejó `RetrievalAgent` conectado a `/v1/query`, pero todavía dentro de un pipeline fijo
de 2 pasos hardcodeado — la decisión "qué agente usar" seguía sin existir. `GraphAgent`/`MemoryAgent`
quedaron construidos y probados, pero standalone, esperando exactamente a esto. Este sprint
construye el primer Planner real: el LLM decide el plan, no el código.

## Qué se construye

- **`packages/core/src/kos_core/schemas/plan.py`** (nuevo): `PlanStep` (promovido desde
  `query_service.py`, con `inputs: dict` sumado), `PlanRequest` (el tipo que doc 03 §5 dibuja en
  el diagrama de secuencia desde el principio pero nunca se había implementado), `Plan`.
- **`packages/core/src/kos_core/json_utils.py`** (promovido desde `apps/workers/.../pipeline/`):
  el helper de `strip_code_fence` que ya usaban `s7_entities`/`s8_relations` para tolerar que
  Ollama envuelva JSON en fences de markdown — el Planner lo necesita también, así que se movió a
  core en vez de duplicarlo.
- **`packages/agents/src/kos_agents/writing.py`** — `WritingAgent`: la síntesis que vivía inline
  en `query_service.answer_query` (`_build_context`, `_SYSTEM_PROMPT`, `llm.generate`) ahora es un
  agente real con el mismo contrato `AgentRequest`/`AgentResponse` que Retrieval/Graph/Memory.
- **`packages/agents/src/kos_agents/planner/`** (nuevo):
  - `planner.py::Planner` — pide al LLM un plan en JSON (catálogo: `retrieval`, `graph` acotado a
    `query` con `template=most_connected|nodes_by_type` — sin resolver `node_id` por nombre, fuera
    de alcance de este sprint —, y siempre cerrando en `writing`). Parseo tolerante (mismo patrón
    que s7/s8) con un reintento con el error adjunto; si falla dos veces, cae al plan fijo
    retrieval→writing de Sprint 17 con `degraded=true` (doc 03 §3 regla 4, algoritmo ahora
    documentado en `docs/03-arquitectura-de-agentes.md`).
  - `executor.py::execute_plan` — agrupa pasos por dependencias resueltas, corre cada grupo en
    paralelo (`asyncio.gather`, doc 03 §3 regla 1), inyecta evidencia fusionada + confidence máxima
    en el paso `writing` automáticamente.
- **`query_service.answer_query`** se simplifica a un wrapper delgado: arma `PlanRequest`, llama al
  `Planner`, traduce a `QueryResult` — la forma de `QueryResponse` no cambió.
- **Doc 03 §3 regla 4** y **doc 10 §7** actualizados con el algoritmo de fallback concreto y la
  corrección de dónde vive `Plan`/`PlanStep` (cruza el límite `kos_agents`↔`apps/api`, terminó en
  `packages/core`, no en `planner/plan.py` como preveía el árbol original).

## Verificación

Contra infra real en todo momento: `POST /v1/query` real (servidor real, no `TestClient`) con una
pregunta que se beneficia del grafo generó un plan dinámico de 2 pasos (`graph`+`writing`); una
pregunta puramente factual redujo a `retrieval`+`writing` con IDs elegidos libremente por el LLM
(no hardcodeados); un LLM de planificación roto forzado a mano cayó al plan fijo con
`degraded=true` tras 2 intentos, sin romper la respuesta (la síntesis siguió usando el LLM real).
`scripts/demo_sprint18.py` reproduce los tres escenarios. 287 tests unitarios + 30 de integración
(38 nuevos/tocados este sprint), ruff, `mypy --strict` (core) e import-linter limpios.

## Bugs encontrados y arreglados (dos, ambos solo visibles contra infra real)

1. **Evidencia de grafo sin contenido citable**: `GraphAgent._node_evidence` nunca completaba
   `EvidenceRef.quote` — `WritingAgent._build_context` armaba una cita vacía para cada nodo, y el
   LLM concluía "no hay evidencia" pese a que el plan sí había traído nodos reales. Nadie lo había
   notado en Sprint 17 porque `GraphAgent` nunca se había conectado a la síntesis (standalone).
   Arreglado agregando `quote=f"{name} ({node_type})"`.
2. **Un paso de evidencia que falla tumbaba toda la request con 500**: el LLM propuso
   `node_type: "*"` (intentando decir "sin filtro") para un paso de grafo — inválido contra la
   ontología cerrada (doc 02 regla 1), y la excepción se propagaba sin capturar hasta un 500
   genérico. Arreglado en `executor.py`: un paso de evidencia (`retrieval`/`graph`) que falla ahora
   degrada a evidencia vacía (`outputs={"degraded": true}`) en vez de romper el plan — mismo
   espíritu que la degradación a búsqueda léxica cuando falla el embedder (doc 06: mejor algo que
   nada). El paso `writing` es la excepción deliberada: su fallo sí se propaga (no hay evidencia
   razonable con la que degradar una síntesis), mapeado a 503 como ya hacía `SynthesisError`.

## Qué se recorta (deuda visible)

- El catálogo de `graph` en el Planner está acotado a `query` (`most_connected`/`nodes_by_type`):
  `get_node`/`find_path` necesitarían un paso previo de resolución de entidad por nombre → id, que
  no existe todavía — el LLM no puede pedir "el vecindario de FastAPI" directamente, solo
  "los nodos más conectados" o "los nodos de tipo X". Ampliar esto es trabajo futuro, no bloquea
  la demo de este sprint.
- `MemoryAgent` sigue fuera del catálogo del Planner — decisión explícita, Sprint 21 lo conecta
  junto con el `LearningAgent` (doc 04 §3 "Recuperación").
- Sin presupuestos reales todavía (`Constraints.timeout_s`/`max_steps` se pasan pero no se
  exigen) — Sprint 19 los hace cumplir de verdad con degradación observable.
- El plan generado no se persiste (`GET /v1/plans/{id}` sigue sin existir) — Sprint 19.

## Qué se aprendió

- **Verificar contra infra real encontró, otra vez, dos bugs reales que los tests con fakes nunca
  hubieran atrapado**: la evidencia de grafo sin `quote` solo se nota cuando de verdad se le pide
  al LLM sintetizar con esa evidencia real (los tests unitarios de `GraphAgent`/Sprint 17 nunca
  ejercitaron ese camino porque el agente era standalone); el `node_type: "*"` solo aparece cuando
  un LLM real, con su propia interpretación de "sin filtro", genera el plan — un test con fakes
  jamás hubiera propuesto ese valor por su cuenta. Mismo patrón que ya se repitió en Sprints
  8/9/12/13/14/16/17 de este proyecto.
- Separar "qué degrada gracefully" (pasos de evidencia) de "qué debe propagar su fallo" (síntesis)
  en el executor fue la decisión de diseño más importante del sprint — sin esa distinción, o todo
  fallo se traga silenciosamente (ocultando fallos reales de síntesis) o todo fallo tumba la
  request (como pasó con el bug de `node_type`).
