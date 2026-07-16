# ADR-0005 — MCP como protocolo único de herramientas

**Estado:** Aceptado
**Fecha:** 2026-07-11

## Contexto

Los agentes necesitan herramientas: leer PDFs, escribir notas en Obsidian, buscar en GitHub, abrir el navegador, crear roadmaps. Cada herramienta podría exponerse como función Python interna, endpoint HTTP propio, o mediante un protocolo estándar. Además, la visión de plataforma (Fase 6) incluye un marketplace de herramientas de terceros.

## Decisión

Toda herramienta se expone como servidor **MCP (Model Context Protocol)**, incluso las internas (`vector.search`, `graph.query`, `memory.recall`). Los agentes consumen herramientas exclusivamente a través del catálogo MCP; ningún agente importa clientes de bases de datos directamente.

## Alternativas consideradas

- **Funciones internas + registry propio** — menos overhead hoy, pero protocolo casero que habría que documentar, versionar y abrir a terceros más tarde. Descartada.
- **Híbrido (internas nativas, externas MCP)** — dos vías de invocación, dos modelos de permisos y trazas. La uniformidad vale más que la latencia ahorrada. Descartada.

## Consecuencias

- Positivas: catálogo dinámico (añadir un servidor MCP amplía el sistema sin redesplegar); permisos y trazas uniformes; las herramientas de KOS sirven directamente en cualquier cliente MCP (Claude, IDEs); base natural del marketplace.
- Negativas: overhead de serialización en llamadas internas calientes; si alguna medición lo exige, se permitirá un bypass puntual documentado con su propio ADR.
- El modelo de permisos (escrituras requieren aprobación) se implementa una sola vez, en la capa MCP.
