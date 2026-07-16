# packages/agents

**Planner y agentes especializados.** Solo dependen de `packages/core`.

Agentes: Planner, Retrieval, Graph, Memory, Research, Writing, Learning. Cada consulta se resuelve con un plan de ejecución explícito, trazable y auditable — nunca con una única llamada al LLM.

Los agentes consumen herramientas exclusivamente vía MCP ([ADR-0005](../../docs/adr/0005-mcp-como-protocolo-de-herramientas.md)).

- Diseño completo: [docs/03-arquitectura-de-agentes.md](../../docs/03-arquitectura-de-agentes.md)
- Se implementa en la **Fase 4** (v0.5); antes, la API usa un pipeline fijo con los mismos contratos.
