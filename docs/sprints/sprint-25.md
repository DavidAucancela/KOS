# Retro — Sprint 25: "Aceptar o descartar"

**Estado:** ✅ Cerrado 2026-08-17. Cuarto sprint de v1.0 — Recomendador (Fase 5).

## Motivación

Sprints 22-24 dejaron dos tipos reales de recomendación (lagunas, contradicciones) generándose y
persistiéndose, pero sin ningún camino para que el usuario reaccione a ellas — `GET
/v1/recommendations` solo lee. Este sprint cierra el loop de feedback (doc 11 §8) y les da una
superficie mínima en la UI.

## Hallazgo real al implementar

`has_pending_recommendation` (Sprint 23) solo bloqueaba regeneración mientras el estado fuera
`pending` — un descarte real dejaba la firma (`type` + `target_entities`) libre para que la
siguiente pasada del Recomendador volviera a proponer exactamente lo mismo que el usuario acababa
de rechazar. Es justo lo que doc 11 §8 pedía evitar ("descartar debe suprimir la regeneración
inmediata"), pero nunca se había ejercitado porque hasta ahora no existía forma de descartar nada.
Se renombró a `has_active_recommendation` y se amplió para bloquear también `accepted`/
`dismissed` — solo `expired`/`superseded` (sin uso real todavía) no bloquean.

## Qué se construye

- **`packages/core/src/kos_core/storage/postgres.py`**: `has_active_recommendation()` (renombrada
  y ampliada) + `update_recommendation_status()` — nuevo, fija `resolved_at`, solo actúa sobre
  `pending` (idempotente contra doble-click, mismo criterio que `archive_memory`).
- **`apps/api/.../routes/recommendations.py`**: `PATCH /v1/recommendations/{id}` (`{status:
  accepted|dismissed, reason?}`) — 404 si no existe o ya está resuelta.
- **`apps/web/src/features/recommendations/`** (nuevo): `useRecommendations` (fetch de pendientes
  + `resolve()`, mismo patrón de fetch directo que `useHealth`/`usePlan`) y `RecommendationsPanel`
  — lista de recomendaciones pendientes con Aceptar/Descartar (razón opcional en un input que
  aparece al descartar), embebida en `StatusPage` sin pestaña/panel nuevo en el nav (doc 11 §7).

`RecommenderAgent`, `recommendations.store`, `gaps_by_prerequisite` y
`_default_contradiction_verdict` no cambiaron — el feedback loop es puramente de lectura/escritura
de estado, no toca la generación.

## Verificación

Contra infra real (API real en un puerto separado del proyecto no relacionado que ya ocupaba el
8000 en la máquina, Postgres real, sin mocks): se insertó una recomendación real `pending`, `GET
/v1/recommendations?status=pending` la mostró, `PATCH .../{id}` con `{status: dismissed, reason:
"smoke test"}` la resolvió (`resolved_at` seteado, `dismissed_reason` guardado) y desapareció de
la lista de pendientes — confirmado con `curl` directo contra la API real, sin TestClient.

Tipos de frontend regenerados desde el OpenAPI real (`openapi-typescript` contra la API corriendo)
— confirmó `PatchRecommendationRequest`/`RecommendationPage` en `schema.d.ts` antes de escribir
ningún componente, siguiendo la regla de doc 09 §3 ("los tipos de la API no se escriben a mano").

Un bug real de robustez apareció corriendo la suite de vitest completa (no en el desarrollo
aislado del componente): `StatusPage.test.tsx` stubea `fetch` globalmente devolviendo siempre la
respuesta de `/health`, sin importar la URL — como `RecommendationsPanel` ahora también vive en
esa página y llama a `/v1/recommendations`, el hook recibía el body de `/health` (sin `items`) y
`items.length` explotaba sobre `undefined`. Arreglado en dos frentes: el hook ahora valida la
forma de la respuesta (`Array.isArray(body.items) ? body.items : []`, defensivo ante cualquier
respuesta inesperada, no solo la del test) y el mock de `StatusPage.test.tsx` pasó a rutear por
URL en vez de responder lo mismo a cualquier `fetch`.

367 tests unitarios (4 nuevos: ruta `PATCH`) + 46 de integración (5 nuevos: dedup ampliado +
`update_recommendation_status`; el único fallo sigue siendo el preexistente
`test_busqueda_lexica_vectorial_e_hibrida`, sin relación) + 28 tests de `apps/web` (4 nuevos,
`RecommendationsPanel`), ruff, `mypy --strict` (core), import-linter y eslint limpios. `tsc -b`
tiene un error preexistente en `TracesPage.test.tsx` (tipo de `PlanStep.post` incompatible,
confirmado por diff que no toca ninguna línea existente de `schema.d.ts` — ya estaba en `main`
antes de este sprint, no es una regresión).

## Qué se recorta (deuda visible)

- Sin UI de historial de recomendaciones resueltas (`accepted`/`dismissed`) — la superficie mínima
  solo muestra `pending`. Suficiente para el criterio de éxito de v1.0, no para auditoría completa.
- El `tsc -b` preexistente sobre `TracesPage.test.tsx`/`PlanStep.post` sigue sin arreglarse — fuera
  de alcance de este sprint (no relacionado con recomendaciones), queda como deuda visible.
- Sin badge de conteo en el nav — la visibilidad depende de entrar a "Estado".

## Qué se aprendió

- Un guardarraíl de dedup escrito para un caso (Sprint 23: evitar reinsertar mientras está
  `pending`) puede quedar incompleto para el caso que en verdad importa (Sprint 25: evitar
  reinsertar después de que el usuario ya dijo que no) sin que ningún test lo note — porque hasta
  que no existe el camino que ejercita el segundo caso, no hay forma de escribir el test que lo
  cubra. Vale la pena releer los guardarraíles existentes cuando se agrega la funcionalidad que
  finalmente los pone a prueba de verdad.
- Correr la suite de tests completa (no solo los del archivo nuevo) encontró un bug de integración
  entre features que el desarrollo aislado del componente no iba a encontrar nunca — el mock
  global de otro archivo de test interactuando con un componente que ese archivo no sabía que
  existía.
