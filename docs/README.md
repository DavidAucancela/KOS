# Documentación de arquitectura — KOS

Estos documentos son la **fuente de verdad del diseño**. Ninguna fase de desarrollo comienza sin que su documento correspondiente esté cerrado y revisado.

## Índice

| # | Documento | Fase que habilita | Estado |
|---|---|---|---|
| 00 | [Visión y objetivos](00-vision-y-objetivos.md) | Todas | 🟢 Aprobado |
| 01 | [Arquitectura general](01-arquitectura-general.md) | Todas | 🟢 Aprobado |
| 02 | [Modelo de dominio y ontología](02-modelo-de-dominio-y-ontologia.md) | Fase 1–2 | 🟢 Aprobado |
| 03 | [Arquitectura de agentes](03-arquitectura-de-agentes.md) | Fase 4 | 🟢 Aprobado (implementado, v0.5 cerrado 2026-08-16) |
| 04 | [Memoria y aprendizaje](04-memoria-y-aprendizaje.md) | Fase 3 | 🟢 Aprobado (implementado, v0.4 cerrado 2026-08-15) |
| 05 | [Ingesta y actualización](05-ingesta-y-actualizacion.md) | Fase 1 | 🟢 Aprobado |
| 06 | [APIs y contratos](06-apis-y-contratos.md) | Fase 1+ | 🟢 Aprobado |
| 07 | [Roadmap por versiones](07-roadmap-versiones.md) | Planificación | 🟡 Borrador (v0.1–v0.5 cerradas, v1.0 construcción completa en ventana de medición) |
| 08 | [Plan de sprints](08-plan-de-sprints.md) | Planificación | 🟡 Borrador (Sprint 0–26 cerrados; siguiente: deuda técnica, no sprint numerado) |
| 09 | [Guía de desarrollo y despliegue](09-guia-desarrollo-y-despliegue.md) | Todas | 🟢 Aprobado |
| 10 | [Estructura del proyecto](10-estructura-del-proyecto.md) | Todas | 🟢 Aprobado |
| 11 | [Recomendador e inteligencia proactiva](11-recomendador-e-inteligencia-proactiva.md) | Fase 5 | 🔵 En revisión (implementado, construcción cerrada 2026-08-18; promueve a 🟢 al confirmar el criterio de salida de v1.0) |
| 12 | [Calidad de extracción: entidades y relaciones cross-documento](12-calidad-de-extraccion-de-entidades-y-relaciones.md) | Mejora sobre Fase 1 | 🟡 Borrador |
| 13 | [Interfaz de usuario](13-interfaz-de-usuario.md) | Mejora sobre Fase 1+ | 🟡 Borrador (implementado 2026-08-27: colapso de paneles, vista de memoria, animación/caminos del grafo) |
| 14 | [Despliegue en Railway (single-tenant, mínimo coste)](14-despliegue-en-railway.md) | Opción de despliegue sobre doc 09 §7 | 🟡 Borrador (no planificado en roadmap; requiere ADR de proveedor cloud) |

Estados: 🟡 Borrador → 🔵 En revisión → 🟢 Aprobado. Un doc marcado "implementado" ya tiene código
real construido sobre él — cambiarlo requiere PR igual que cualquier documento en revisión, no
relajar la disciplina porque el sprint ya haya cerrado.

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

## Deuda técnica

[`docs/deuda-tecnica.md`](deuda-tecnica.md) — registro vivo de lo que cada retro de sprint dejó
pendiente, consolidado en un solo lugar. Se actualiza al cerrar cada sprint, no es un documento de
diseño.

## Próximo paso (tras la construcción de v1.0)

v1.0 (Recomendador) terminó su construcción el 2026-08-18 (Sprints 22–26); su criterio de salida
(≥1 recomendación útil/semana) se mide con calendario real hasta el 2026-09-18, no con una demo de
sprint — mientras esa ventana corre, el trabajo activo son tres frentes sobre
[`docs/deuda-tecnica.md`](deuda-tecnica.md), en este orden:

1. **Deuda técnica** — ítems "sin sprint asignado" y "UI/UX baja prioridad". Evaluar el riesgo real
   de cada ítem antes de implementarlo, no asumir que "cerrar deuda" siempre es la acción correcta
   — un ítem puede evaluarse y quedar documentado como decisión de NO resolverlo (ver el caso de
   `memory.store` en el catálogo del Planner).
2. **Mejoras de calidad** — sección "Calidad / ajuste fino": desambiguación léxica, clasificación
   de entidades, umbrales sin tuning, precisión conservadora del veredicto de contradicción.
3. **Monitoreo** — doc 09 §6 define métricas de negocio, pero hoy solo cubren ingesta/búsqueda; no
   hay métricas del Planner, los agentes ni el Recomendador. Revisar doc 09 §6 antes de sumar
   instrumentación nueva.

v1.1 (Plataforma) no se planifica en sprints hasta cerrar el criterio de salida de v1.0 — regla 1
del roadmap (doc 07).

## Cómo proponer un cambio de diseño

1. Si es una decisión puntual → nuevo ADR usando [la plantilla](adr/0000-plantilla.md).
2. Si afecta a un documento completo → PR modificando el documento, con el razonamiento en la descripción.
3. Los documentos aprobados (🟢) solo cambian mediante PR revisada.
