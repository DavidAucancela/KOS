# 07 — Roadmap por versiones (v0.1 → v1.0)

**Estado:** 🟡 Borrador · **Última actualización:** 2026-07-11

Cada versión corresponde a una fase de la arquitectura y termina en algo **usable**, no en infraestructura suelta. Las duraciones asumen dedicación parcial tipo side-project intenso; son estimaciones, no compromisos.

```
v0.1 ──► v0.2 ──► v0.3 ──► v0.4 ──► v0.5 ──► v1.0
Fund.    Core     Grafo    Memoria  Agentes  Proactivo+Plataforma
```

## v0.1 — Fundaciones (Fase 0) · 2–3 semanas

**Meta:** entorno completo y arquitectura documentada. Ninguna línea de producto sin diseño detrás.

- [x] Monorepo con estructura de dominios
- [x] Documentos de arquitectura 00–09 en borrador
- [x] ADRs de las decisiones estructurales
- [x] Docker Compose: Postgres+pgvector, Neo4j, Redis, MinIO, Ollama
- [x] CI (GitHub Actions) esqueleto
- [ ] Documentos 00–02 y 05 revisados y aprobados (🟢)
- [ ] Modelos de Ollama descargados y probados (bge-m3, LLM local)
- [ ] Scaffold de `apps/api` (FastAPI + health + config) y `apps/web` (Vite)

**Criterio de salida:** `make up` levanta todo; los docs que habilitan la Fase 1 están 🟢.

## v0.2 — Knowledge Core (Fase 1) · 4–6 semanas

**Meta:** *responder preguntas con citas provenientes de tus notas.*

- Conectores: Obsidian, PDF, Git (interfaz `Connector` estable)
- Modelo unificado de documentos + almacenamiento (MinIO + Postgres)
- Pipeline del parser etapas 1–6 (normalización → chunking → embeddings → resumen)
- Búsqueda híbrida (BM25/trgm + pgvector) con fusión de resultados
- `POST /v1/query` con síntesis LLM y evidencia obligatoria
- UI mínima: chat + lista de fuentes + visor de citas

**Criterio de salida:** >90% de preguntas de un set de evaluación propio respondidas con ≥1 cita correcta sobre el vault real (~1.000 notas).

## v0.3 — Knowledge Graph (Fase 2) · 5–7 semanas

**Meta:** *navegar el conocimiento por relaciones, no solo por similitud.*

- Ontología v1 implementada y validada ([doc 02](02-modelo-de-dominio-y-ontologia.md))
- Etapas 7–8 del parser: extracción de entidades y relaciones con confianza
- Entity resolution (dedupe + merge)
- Neo4j como fuente de verdad de relaciones; sincronización doc_id ↔ grafo
- Endpoints `/v1/graph/*` + correcciones manuales del usuario
- Visualización del grafo en la UI (panel derecho)

**Criterio de salida:** precisión de extracción >80% validada a mano sobre una muestra; el caso de uso "¿qué conecta X con Y?" funciona.

## v0.4 — Memoria y aprendizaje (Fase 3) · 4–5 semanas

**Meta:** *el sistema evoluciona sin intervención manual.*

- Los 5 tipos de memoria + `MemoryItem` ([doc 04](04-memoria-y-aprendizaje.md))
- Learning pipeline: evento → embeddings → grafo → memoria, incremental e idempotente
- Watcher de Obsidian: cambio en el vault reflejado en <5 min
- Sistema de confianza transversal + versionado de documentos
- Detección de duplicados con propuesta de fusión
- Auditoría de memoria en la UI (`/v1/memory`)

**Criterio de salida:** editar/crear/borrar notas y ver el sistema actualizado solo, con traza de qué cambió y por qué.

> **v0.4 cerrado 2026-08-15** (Sprints 12–15, `docs/sprints/sprint-12.md` a `sprint-15.md`):
> los 5 tipos de memoria + `MemoryItem`, pipeline de aprendizaje (`kos.memory_learn`/
> `kos.memory_consolidate`), sistema de confianza transversal con recálculo al perder una fuente
> (grafo y memoria), entity-linking de memoria contra el grafo, y auditoría vía `GET`/`DELETE
> /v1/memory`. Criterio de salida cumplido para grafo/memoria vía la propagación de
> `document.deleted` (Sprint 11 + Sprint 14). Deuda que queda documentada, no bloquea el cierre:
> **sin UI de auditoría de memoria** en `apps/web` (solo API — a diferencia del grafo, que sí
> tiene pantalla propia desde Sprint 10); sin corrección manual de memoria (`locked`, análogo a
> Sprint 9 en el grafo); detección de duplicados con fusión propuesta (doc 04 §6) implementada
> como consolidación automática determinística, no como propuesta que el usuario aprueba — la
> autonomía configurable queda para Fase 5 según ya preveía doc 04 §6.

## v0.5 — Orquestación de agentes (Fase 4) · 6–8 semanas

**Meta:** *cada consulta se resuelve con un plan de ejecución.*

- Planner real generando planes dinámicos ([doc 03](03-arquitectura-de-agentes.md))
- Agentes Retrieval, Graph, Memory, Research, Writing, Learning sobre los contratos ya existentes
- Herramientas externas MCP (GitHub, web)
- Trazas completas de plan visibles en la UI (`/v1/plans/{id}`)
- Presupuestos y degradación elegante

**Criterio de salida:** una consulta compleja produce un plan multi-paso inspeccionable que combina vector + grafo + memoria + web.

## v1.0 — Inteligencia proactiva + base de plataforma (Fases 5–6 parciales) · 8–10 semanas

**Meta:** *el sistema genera valor sin que le hagas preguntas.*

- Recomendador: lagunas de conocimiento, roadmaps personalizados, contradicciones, relaciones descubiertas, reorganización de Obsidian propuesta
- SDK mínimo de conectores (un tercero puede escribir uno sin tocar el núcleo)
- API pública estable `/v1` + documentación
- Empaquetado: instalación reproducible en una máquina nueva en <30 min

**Criterio de salida:** ≥1 recomendación útil no solicitada por semana durante un mes de uso real; un conector externo de ejemplo (p.ej. carpeta de HTML) escrito solo contra el SDK.

## Después de v1.0 (no comprometido)

Multi-usuario y workspaces, permisos, marketplace MCP, panel de administración, más conectores (Notion, Gmail, Slack, Discord, Jira, Confluence, WhatsApp, transcripciones, vídeo/audio, SQL, APIs), Kubernetes, Temporal.

## Reglas del roadmap

1. No se empieza una versión sin cerrar el criterio de salida de la anterior.
2. Los docs que habilitan una fase deben estar 🟢 antes de escribir su código.
3. Todo lo aprendido que contradiga el diseño → ADR antes de desviarse.
