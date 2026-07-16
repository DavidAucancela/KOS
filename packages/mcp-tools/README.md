# packages/mcp-tools

**Servidores MCP de KOS.** Solo dependen de `packages/core`.

Toda herramienta (interna o externa) se expone por MCP: `vector.search`, `graph.query`, `memory.recall`, `obsidian.create_note`, `github.search_repos`, `web.search`… Convención: `<dominio>.<verbo>_<objeto>`.

Las herramientas de escritura requieren aprobación del usuario por defecto; toda invocación se registra con el `trace_id` del plan que la causó.

- Catálogo y reglas: [docs/06-apis-y-contratos.md](../../docs/06-apis-y-contratos.md) (sección 4)
- Decisión: [ADR-0005](../../docs/adr/0005-mcp-como-protocolo-de-herramientas.md)
