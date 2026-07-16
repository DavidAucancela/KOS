# Documentación de arquitectura — KOS

Estos documentos son la **fuente de verdad del diseño**. Ninguna fase de desarrollo comienza sin que su documento correspondiente esté cerrado y revisado.

## Índice

| # | Documento | Fase que habilita | Estado |
|---|---|---|---|
| 00 | [Visión y objetivos](00-vision-y-objetivos.md) | Todas | 🟢 Aprobado |
| 01 | [Arquitectura general](01-arquitectura-general.md) | Todas | 🟢 Aprobado |
| 02 | [Modelo de dominio y ontología](02-modelo-de-dominio-y-ontologia.md) | Fase 1–2 | 🟢 Aprobado |
| 03 | [Arquitectura de agentes](03-arquitectura-de-agentes.md) | Fase 4 | 🟡 Borrador |
| 04 | [Memoria y aprendizaje](04-memoria-y-aprendizaje.md) | Fase 3 | 🟡 Borrador |
| 05 | [Ingesta y actualización](05-ingesta-y-actualizacion.md) | Fase 1 | 🟢 Aprobado |
| 06 | [APIs y contratos](06-apis-y-contratos.md) | Fase 1+ | 🟢 Aprobado |
| 07 | [Roadmap por versiones](07-roadmap-versiones.md) | Planificación | 🟡 Borrador |
| 08 | [Plan de sprints](08-plan-de-sprints.md) | Planificación | 🟡 Borrador |
| 09 | [Guía de desarrollo y despliegue](09-guia-desarrollo-y-despliegue.md) | Todas | 🟢 Aprobado |
| 10 | [Estructura del proyecto](10-estructura-del-proyecto.md) | Todas | 🟢 Aprobado |

Estados: 🟡 Borrador → 🔵 En revisión → 🟢 Aprobado

## ADRs (Architecture Decision Records)

Las decisiones técnicas puntuales se registran en [`adr/`](adr/). Cada ADR captura el contexto, la decisión y sus consecuencias. Una decisión aprobada solo se revierte con un nuevo ADR que la reemplace.

| ADR | Decisión |
|---|---|
| [0001](adr/0001-nucleo-independiente-de-fuentes.md) | El núcleo es independiente de las fuentes; Obsidian es un conector |
| [0002](adr/0002-postgres-pgvector-como-vector-db.md) | PostgreSQL + pgvector como base vectorial |
| [0003](adr/0003-neo4j-como-fuente-de-verdad-del-grafo.md) | Neo4j como fuente de verdad de las relaciones |
| [0004](adr/0004-monorepo.md) | Monorepo para todo el sistema |
| [0005](adr/0005-mcp-como-protocolo-de-herramientas.md) | MCP como protocolo único de herramientas |
| [0006](adr/0006-local-first-con-ollama.md) | Local-first: Ollama como runtime de LLM por defecto |

## Cómo proponer un cambio de diseño

1. Si es una decisión puntual → nuevo ADR usando [la plantilla](adr/0000-plantilla.md).
2. Si afecta a un documento completo → PR modificando el documento, con el razonamiento en la descripción.
3. Los documentos aprobados (🟢) solo cambian mediante PR revisada.
