# Retro — Sprint 15: cierre de v0.4

**Estado:** ✅ Cerrado 2026-08-15. Cierra v0.4 — Memoria y aprendizaje (Fase 3).

## Motivación

Sprint 12 dejó la ruta de consolidación (`kos.memory_consolidate`) cubierta solo por tests con
fakes: verificarla en vivo con 3 preguntas reales repetidas competía por el mismo Ollama local que
la sincronización del vault, y no hubo ventana libre en ese momento. Con Sprints 13 y 14 cerrando
las otras dos deudas de v0.4 (entity-linking, recálculo de confidence), este sprint cierra la
última pieza pendiente y revisa qué queda abierto antes de dar la versión por terminada.

## Qué se hace

- **Demo de consolidación en vivo**: misma pregunta real (`"¿qué es FastAPI?"`) enviada 3 veces a
  `POST /v1/query` contra el vault real, con Ollama libre de contención esta vez. Las 3 respuestas
  (casi idénticas, variación normal del LLM) generaron 3 memorias episódicas con embeddings lo
  bastante similares para superar `DUPLICATE_THRESHOLD` (0.92). `kos.memory_consolidate`,
  disparada por el worker Celery real, las agrupó en una memoria semántica nueva y marcó las 3
  episódicas con `superseded_by` apuntando a ella — verificado vía `GET /v1/memory`. A diferencia
  del demo de Sprint 14, esta memoria queda en la base real (no es data sintética de prueba): son
  preguntas reales sobre el vault real, coherente con lo que el sistema está destinado a aprender.
- **Revisión de deuda de v0.4** (doc 07, roadmap): confirmado con el usuario que la UI de
  auditoría de memoria (única pieza de v0.4 sin construir — `apps/web` no tiene pantalla de
  memoria, a diferencia del grafo desde Sprint 10) queda como deuda documentada, no bloquea el
  cierre. Roadmap actualizado con la nota de cierre de v0.4.

## Verificación

Contra infra real (misma sesión que Sprint 13/14: `make up`, worker Celery, API, Ollama nativo):
la memoria semántica `9e7a068e-d52b-4594-b42d-6c885670d098` agrupa las 3 episódicas reales sobre
FastAPI, visible en `GET /v1/memory?type=semantic`. Sin cambios de código este sprint — es
verificación operativa, no desarrollo (mismo patrón que anticipaba la retro de Sprint 12).

## Qué queda abierto (deuda visible, heredada a v0.5)

- **Sin UI de auditoría de memoria** en `apps/web`. Decisión explícita del usuario (2026-08-15):
  no bloquea el cierre de v0.4; se revisita cuando haya pantallas nuevas que construir de todos
  modos (candidato natural: junto con las trazas de plan de v0.5, doc 07 §v0.5).
- **Sin corrección manual de memoria** (`locked`, análogo a la corrección de nodos del grafo de
  Sprint 9): no hay caso de uso real que lo haya pedido todavía.
- **Detección de duplicados es automática, no propuesta**: `kos.memory_consolidate` fusiona sin
  pedir aprobación — doc 04 §6 ya preveía que la autonomía configurable (usuario aprueba vs.
  sistema decide solo) es de Fase 5, así que esto no es deuda nueva, es el diseño original.

## Qué se aprendió

- Verificar en vivo lo que quedó cubierto "solo por tests" vale la pena incluso cuando parece
  redundante: la demo de Sprint 12 con fakes ya probaba la lógica de clustering correctamente,
  pero solo la corrida real confirma que 3 respuestas del LLM a la misma pregunta (con su
  variación natural de temperatura) efectivamente superan el umbral de similitud en la práctica,
  no solo en el caso de prueba construido a mano.
- La ventana de contención de recursos (Ollama local compartido con la sincronización del vault)
  que bloqueó esto en Sprint 12 fue puramente circunstancial — no hizo falta ningún cambio de
  infraestructura para resolverlo, solo correr la verificación en un momento sin esa contención.
