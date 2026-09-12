# ADR-0007 — Proveedor cloud (OpenAI) opt-in por tarea para Planner y WritingAgent

**Estado:** Aceptado
**Fecha:** 2026-08-29

## Contexto

Cada `POST /v1/query` hace al menos dos llamadas secuenciales al LLM local
(llama3.2 vía Ollama): el Planner genera el plan y el WritingAgent sintetiza la
respuesta final con citas. En el hardware local del usuario cada generación tarda
varios segundos, así que las consultas interactivas se sienten lentas.

ADR-0006 ya previó este caso: el acceso al LLM pasa por el Protocol `LLMClient`
en `packages/core`, con implementaciones intercambiables, y "el usuario puede
configurar un proveedor cloud por tarea de forma explícita y opt-in". Hasta ahora
solo existía `OllamaLLMClient` y no había selección de proveedor. Este ADR
concreta ese punto para las dos tareas interactivas, sin tocar la ingesta.

## Decisión

Se añade una ruta cloud **opt-in, por tarea, apagada por defecto**, para el
Planner (generación de plan) y el WritingAgent (síntesis). Proveedor: OpenAI vía
el SDK `openai`. La ingesta, la extracción de grafo, la consolidación de memoria
y los embeddings siguen siendo **exclusivamente locales** y no son configurables
a cloud.

- **Selección**: `kos_planner_llm_provider` y `kos_writing_llm_provider`
  (`"ollama"` | `"openai"`). Si es `"openai"` sin `openai_api_key`, se cae a
  Ollama con un warning — nunca un fallo al arrancar.
- **Puerta de privacidad (Writing)**: la síntesis solo va a cloud si la evidencia
  no está vacía **y** todo `EvidenceRef` tiene `cloud_safe is True`. `cloud_safe`
  deriva de un booleano por fuente en `sources.config` (`cloud_safe: true`),
  resuelto con `COALESCE((s.config ->> 'cloud_safe')::boolean, false)` en las
  consultas de búsqueda. La evidencia de grafo y de memoria no tiene fila de
  fuente que clasificar y queda siempre `cloud_safe=False`. Cualquier fragmento
  no seguro fuerza la síntesis completa a local. Es un mecanismo **interino**
  hasta que exista un clasificador real de contenido privado/público.
- **Puerta de privacidad (Planner)**: el prompt de generación de plan es solo el
  texto de la pregunta del usuario (sin corpus). Se decide por
  `kos_planner_llm_provider` + presencia de key. **Riesgo aceptado explícito**:
  la pregunta del usuario puede contener texto privado y se enviaría a OpenAI
  cuando el proveedor del Planner sea cloud. Mitigación: Planner cloud apagado
  por defecto; un clasificador de consulta futuro puede cerrar esta puerta.
- **Auditoría**: toda llamada cloud emite un métrico (tokens, coste, latencia,
  estado/error, tags `app=kos, task=planner|writing`) a una instancia
  **self-hosted** de llm-observatory
  (github.com/DavidAucancela/llm-observatory) vía su SDK `AsyncMonitoredOpenAI`.
  El SDK persiste además prompt y respuesta en la BD del observatory; se acepta
  porque es infra propia y la puerta `cloud_safe` garantiza que solo contenido ya
  autorizado a salir a OpenAI llega a esa ruta.
- **Cadena de fallback (soporte offline, ADR-0006)**: cloud →
  (error | timeout | key ausente | bloqueo por privacidad) → Ollama local → ruta
  degradada existente del Planner (`_fixed_plan_steps`) / `SynthesisError` del
  WritingAgent. La ruta cloud se envuelve en `FallbackLLMClient`, que reintenta en
  local ante cualquier excepción.
- **Ubicación del código**: `OpenAILLMClient` y las dependencias (`openai`, SDK
  `llm-observatory`) viven solo en `apps/api`. El Protocol `LLMClient` sigue en
  `packages/core`; no se re-exporta la implementación cloud desde
  `kos_core.llm.__init__`.

## Alternativas consideradas

- **Cambiar el default a cloud** — rompe ADR-0006 (privacidad y coste marginal
  cero por nota). Descartada: cloud es opt-in, Ollama sigue siendo el default.
- **Cloud también para la ingesta / extracción de relaciones** — volumen alto
  (millones de llamadas pequeñas), coste variable por nota y fuga masiva de
  contenido. Descartada para este ADR; la extracción de relaciones puntual queda
  como trabajo futuro con su propia puerta.
- **Switch global sin puerta por fuente** — enviaría contenido privado a OpenAI
  en la primera consulta sobre una fuente no marcada, sin vuelta atrás.
  Descartada: la puerta `cloud_safe` por fuente es requisito.
- **Emisor de métricas metadata-only propio (sin SDK)** — evitaría persistir
  prompt/respuesta fuera de KOS, pero descarta el SDK que el usuario ya
  mantiene. Descartada: se usa el SDK tal cual, mitigado por infra self-hosted +
  puerta `cloud_safe`. Un `capture_content=False` upstream en el SDK sigue siendo
  la mejora preferida a futuro.
- **`OpenAILLMClient` en `packages/core`** — simétrico con `OllamaLLMClient`,
  pero mete `openai` + un SDK vía git en el runtime de todos los workspace
  packages (workers de ingesta incluidos) y amplía la superficie de
  `mypy --strict`. Descartada: la implementación cloud vive en `apps/api`.

## Consecuencias

- Positivas: consultas interactivas notablemente más rápidas cuando cloud está
  activo; auditoría real de token/coste/latencia del path cloud (cubre en parte
  el hueco de monitoreo del Planner/agentes); los workers y la ingesta no
  cambian ni arrastran dependencias nuevas.
- Negativas / deuda aceptada:
  - `EvidenceRef` y `SearchHit` ganan un campo `cloud_safe` (default `False`,
    retrocompatible) y las 4 consultas SQL de búsqueda hacen un `LEFT JOIN
    sources` extra.
  - `sources.config` gana una clave reservada `cloud_safe` que `_build_connector`
    debe descartar antes de instanciar el conector.
  - Marcar una fuente como `cloud_safe` requiere `PATCH /v1/sources/{id}` (nueva
    ruta) — no hay UI.
  - Con cloud activo conviven dos (Planner) o tres (Writing: local + cloud)
    instancias de cliente LLM en `app.state`.
  - El SDK de llm-observatory persiste prompt y respuesta completos en su BD.
  - Sin tope de coste duro: llm-observatory solo observa y alerta (Discord), no
    bloquea llamadas. **Diferido**: contador mensual + corte a local.
  - **Diferido**: clasificador real de contenido privado (hoy la granularidad es
    por fuente); cloud para la extracción de relaciones u otros agentes; opción
    `capture_content=False` upstream en el SDK; publicar imágenes de
    llm-observatory (`api`/`web`) para poder self-hostearla en el compose de KOS.
- Si se revierte: quitar los dos `kos_*_llm_provider` (vuelven a Ollama fijo),
  borrar `apps/api/src/kos_api/llm/`, revertir el wire-up de `main.py`/`query.py`.
  El campo `cloud_safe` puede quedarse (inerte) o quitarse de `EvidenceRef`/
  `SearchHit` + las 4 SQL; no hay migración que revertir.
