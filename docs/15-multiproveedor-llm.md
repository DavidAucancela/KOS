# 15 — Multiproveedor LLM

**Estado:** 🟡 Borrador · **Última actualización:** 2026-09-10 · **Extiende:**
[ADR-0007](adr/0007-proveedor-cloud-opt-in-para-planner-y-writing.md) sobre
[ADR-0006](adr/0006-local-first-con-ollama.md)

> ADR-0007 abrió la primera ruta cloud (OpenAI, opt-in por tarea, para Planner y WritingAgent).
> Este documento especifica qué falta para que "multiproveedor" sea real: qué ya funciona sin
> código, qué exige código, y qué exige un ADR nuevo. **No revierte ninguna decisión de ADR-0006 ni
> de ADR-0007** — la ingesta, la extracción de grafo y los embeddings siguen exclusivamente
> locales, y las implementaciones cloud siguen viviendo en `apps/api`.

## 1. Estado real de partida

Lo construido (ADR-0007, PR #25):

| Pieza | Dónde | Qué hace |
|---|---|---|
| Protocol `LLMClient` / `EmbeddingClient` | `packages/core/src/kos_core/llm/base.py` | Contrato único. El resto del sistema depende solo de esto. |
| `OllamaLLMClient` | `packages/core/src/kos_core/llm/ollama.py` | Única implementación en `core`. Default de todo. |
| `OpenAILLMClient` | `apps/api/src/kos_api/llm/openai_client.py` | Envuelve `AsyncMonitoredOpenAI` (SDK llm-observatory) para auditar token/coste/latencia. |
| `make_llm_client` / `make_writing_clients` | `apps/api/src/kos_api/llm/factory.py` | Elige proveedor por tarea; envuelve cloud en `FallbackLLMClient` (cloud → local). |
| Config | `packages/core/src/kos_core/config.py` | `kos_planner_llm_provider`, `kos_writing_llm_provider`, `openai_api_key`, `openai_llm_model`, `openai_base_url`. |

Las cuatro instanciaciones directas de `OllamaLLMClient` fuera del factory
(`enrich.py`, `recommend.py`, `cross_doc_relations.py`, `graph_sync.py`) son **deliberadas**: son
el path de workers, que ADR-0007 excluyó de cloud. No son deuda, salvo el caso de §5.

### Aclaración: dónde vive el código de proveedor (regla 2 de CLAUDE.md)

La regla 2 exige que **los esquemas** que cruzan fronteras vivan en `packages/core`. El Protocol
`LLMClient` está ahí; las implementaciones concretas no cruzan ninguna frontera — cada app
instancia la suya y la pasa como `LLMClient`. ADR-0007 evaluó explícitamente poner
`OpenAILLMClient` en `core` (simétrico con Ollama) y **lo descartó**: mete `openai` + un SDK vía
git en el runtime de todos los workspace packages, incluidos los workers de ingesta, y amplía la
superficie de `mypy --strict`. Este documento mantiene esa decisión: los proveedores cloud viven
en `apps/api/src/kos_api/llm/`.

## 2. El SDK de auditoría ya cubre 5 proveedores

**Verificado el 2026-09-10** contra `DavidAucancela/llm-observatory`
(`packages/sdk-python`), no asumido. El SDK expone wrappers monitoreados para **cinco** proveedores,
no solo OpenAI:

| Wrapper | Proveedor | Dep | Tabla de precios propia |
|---|---|---|---|
| `AsyncMonitoredAnthropic` | Anthropic (Claude) | `anthropic` — **dependencia base del SDK**, no extra | `ANTHROPIC_PRICING` |
| `AsyncMonitoredOpenAI` | OpenAI | extra `[openai]` | `OPENAI_PRICING` |
| `AsyncMonitoredGemini` | Google | extra `[gemini]` (`google-genai`, wire format propio) | `GEMINI_PRICING` |
| `AsyncMonitoredGrok` | xAI | extra `[grok]` (alias de `openai`, base_url propia) | `GROK_PRICING` |
| `AsyncMonitoredKimi` | Moonshot AI | extra `[kimi]` (alias de `openai`, base_url propia) | `KIMI_PRICING` |

Consecuencia directa: **`anthropic` ya está instalado en `apps/api` hoy**, como dependencia
transitiva de `llm-observatory`. Un `AnthropicLLMClient` nativo no agrega ninguna dependencia
nueva ni pierde auditoría — el bloqueante que este documento asumía en su primera versión no
existe.

### 2.1 Proveedores OpenAI-compatibles sin wrapper propio

Aparte de los cinco, `Settings.openai_base_url` se pasa tal cual al cliente, así que cualquier API
compatible con OpenAI ya es usable **solo configurando**, sin código:

| Proveedor | `openai_base_url` | Nota |
|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | Inferencia muy rápida. **No confundir con Grok (xAI)**, que sí tiene wrapper propio arriba. |
| OpenRouter | `https://openrouter.ai/api/v1` | Ruteo a decenas de modelos detrás del wire format de OpenAI. |
| DeepSeek | `https://api.deepseek.com` | |
| Together / Fireworks | endpoint propio | |
| vLLM / llama.cpp server local | `http://localhost:8000/v1` | Camino local más rápido que Ollama en el mismo hardware, sin salir de ADR-0006. |

**Coste con estos proveedores:** se atribuye contra `OPENAI_PRICING`, que no los conoce. El SDK
**no** miente en silencio: `finalize_metric_pricing` (`_pricing.py`) estampa
`cost_confidence="unknown"` cuando el modelo no está en la tabla de su proveedor, la llamada
consumió tokens y el coste dio $0. O sea: tokens y latencia siguen siendo correctos, y el coste
queda marcado como no confiable en vez de reportarse como cero real. Aceptable; hay que saberlo.

Trabajo de esta sección: **documentar §2.1 en doc 09 y `.env.example`** — hoy nadie sabe que existe.
Cero código.

## 3. Lo que sí requiere código

### 3.1 Proveedores nativos (Anthropic primero)

Anthropic es el único proveedor mayor con wire format propio relevante acá (`messages` API,
`system` como parámetro top-level en vez de un mensaje más). Requiere un `AnthropicLLMClient`
hermano de `OpenAILLMClient`, envolviendo `AsyncMonitoredAnthropic`.

Tras la verificación de §2 esto es **barato**: la dep ya está instalada, la auditoría de
token/coste/latencia funciona igual que en OpenAI, y el trabajo se reduce a traducir el Protocol
`LLMClient` al shape de `messages.create()` — `system` sale de `messages`, `max_tokens` es
**obligatorio** en la API de Anthropic (hay que elegir un default explícito, el Protocol lo tiene
opcional), y el texto se lee de `response.content[0].text` en vez de
`response.choices[0].message.content`.

Gemini (`AsyncMonitoredGemini`) es el siguiente candidato y sí trae dep nueva (`google-genai`);
Grok y Kimi son alias de `openai` con base_url, así que salen casi gratis una vez que exista el
registro de §3.3. Ninguno de los tres se construye hasta que haya una razón real de uso — se
listan para que el registro no se diseñe asumiendo dos proveedores.

### 3.2 Modelo por tarea, no solo proveedor por tarea

Hoy hay `kos_planner_llm_provider` y `kos_writing_llm_provider` (proveedor por tarea) pero un solo
`openai_llm_model` (modelo global). Planner y Writing comparten modelo obligatoriamente, lo cual
anula buena parte del sentido de elegir proveedor por tarea: el caso natural es *modelo rápido y
barato para planificar, modelo capaz para sintetizar con citas*.

Cambio propuesto en `Settings` (retrocompatible, sin migración):

```
kos_planner_llm_model: str = ""   # vacío = hereda openai_llm_model / ollama_llm_model
kos_writing_llm_model: str = ""
```

`OpenAILLMClient.__init__` deja de leer `settings.openai_llm_model` directo y recibe el modelo
resuelto por el factory. Mismo criterio para `OllamaLLMClient` si se quiere modelo local distinto
por tarea (opcional, no bloqueante).

### 3.3 Registro de proveedores en vez de `if provider != "openai"`

`_cloud_enabled()` (`factory.py`) hardcodea `"openai"` en tres ramas, y el `Task = Literal[...]`
está **duplicado** en `factory.py` y `openai_client.py`. Con un solo proveedor cloud es aceptable;
con dos o más se convierte en una cadena de `if`. Propuesta acotada:

- Un dict `_PROVIDERS: dict[str, ProviderSpec]` en `factory.py`, donde cada spec dice qué
  constructor usar y qué setting de API key exige. `"ollama"` es el caso especial "sin key, sin
  fallback".
- `Task` se define una sola vez y se importa.

**No se construye un sistema de plugins.** Tres proveedores en un dict, no un registro dinámico.

## 4. Fallback y coste — sin cambios estructurales

`FallbackLLMClient` (cloud → local) sigue igual: la cadena es de dos eslabones, no de N. Con varios
proveedores cloud configurados **no** se encadenan entre sí — el proveedor elegido para la tarea,
y si falla, Ollama local. Encadenar cloud → cloud → local multiplica el coste de un fallo y
esconde qué proveedor está respondiendo de verdad.

El tope de coste duro sigue **diferido** (deuda registrada de ADR-0007): llm-observatory observa y
alerta por Discord, no bloquea. Sumar proveedores más baratos (Groq/DeepSeek) reduce el riesgo
económico pero no lo cierra. Este documento no lo resuelve; lo deja anotado como precondición si
alguna vez el default deja de ser Ollama.

## 5. Tarea candidata nueva: el veredicto de contradicción del Recomendador

Es el caso con **valor documentado**, no hipotético. `docs/deuda-tecnica.md` registra:

> El veredicto de contradicción (`_default_contradiction_verdict`) con `llama3.2` (modelo chico
> local) es conservador — no confirmó contradicciones ni en casos obviamente contradictorios
> durante la verificación en vivo de Sprint 24 (…) puede tardar en generar la primera
> recomendación real de este tipo.

Y el criterio de salida de v1.0 (≥1 recomendación útil/semana, ventana hasta 2026-09-18) depende
justamente de que el Recomendador produzca algo. Un modelo más capaz en ese paso es la palanca más
directa que tiene este frente.

**Por qué no es "más de lo mismo" (y por qué necesita ADR propio):**

| Factor | Planner / Writing (ADR-0007) | Veredicto de contradicción |
|---|---|---|
| Dónde corre | `apps/api` | `apps/workers` (`recommend.py`), que **no** tiene la dep `openai` |
| Volumen | por request interactiva | `MAX_CONTRADICTION_SEEDS_PER_RUN = 5` por corrida — acotado y barato |
| Qué se envía | pregunta del usuario / evidencia ya filtrada por `cloud_safe` | **pares de chunks del vault en crudo** — sin puerta hoy |
| Auditoría | vía `AsyncMonitoredOpenAI` | habría que llevar el SDK a los workers |

El punto duro es el tercero: mandar chunks del vault a cloud sin puerta contradice el criterio de
ADR-0007. La puerta `cloud_safe` existe por fuente y los chunks tienen fuente, así que es
aplicable — pero decidirlo es una decisión estructural, no una implementación.

**Propuesta:** ADR-0008 acotado a este paso, con la puerta `cloud_safe` exigida sobre **ambos**
chunks del par (si cualquiera de los dos no es seguro, el veredicto se resuelve local, mismo
criterio fail-safe que WritingAgent). Alcance explícito: solo el veredicto, **no**
`gaps_by_prerequisite` (que no llama al LLM) ni la extracción de grafo.

## 6. Fuera de alcance (decidido en otro lado, no se reabre acá)

- **Embeddings cloud** — ADR-0007 los dejó locales; doc 14 §2 los necesitaría para Railway. Ese es
  el ADR de doc 14, no éste.
- **Ingesta y extracción de grafo cloud** — descartado explícitamente en ADR-0007 (volumen alto,
  coste variable por nota, fuga masiva). El backfill de doc 12 §10 (~15 h locales) es el caso que
  más tienta y sigue descartado.
- **Cambiar el default a cloud** — rompe ADR-0006.
- **Streaming** — el Protocol `LLMClient.generate` es no-streaming a propósito. Otro frente.

## 7. Plan de implementación

En orden de coste creciente. Cada punto es una PR.

| # | Qué | Código | Requiere ADR |
|---|---|---|---|
| 1 | Documentar los proveedores OpenAI-compatibles (§2.1) en doc 09 + `.env.example`, incluida la marca `cost_confidence="unknown"` | no | no |
| 2 | Modelo por tarea (§3.2) | sí, chico | no |
| 3 | Registro de proveedores + `Task` deduplicado (§3.3) | sí, chico | no |
| 4 | `AnthropicLLMClient` nativo (§3.1) — dep ya instalada, auditoría cubierta | sí | no |
| 5 | Veredicto de contradicción con proveedor configurable (§5) | sí | **sí — ADR-0008** |

Los puntos 1–4 no reabren ninguna decisión: son extensión directa de ADR-0007 dentro de sus
límites. El 5 es el único que necesita decisión estructural, y también el único con valor medido
(la ventana de v1.0). Si el tiempo alcanza para una sola cosa, es el 5 — pero su ADR se escribe
antes que su código.

Orden sugerido: 3 → 2 → 4 (el registro primero evita reescribir el factory dos veces), con el 1 en
paralelo por ser solo docs, y el 5 arrancando por el ADR.

## 8. Riesgos y preguntas abiertas

1. **Coste marcado como no confiable** con proveedores OpenAI-compatibles fuera de la tabla
   (§2.1). No es un riesgo de datos falsos — el SDK lo estampa — pero sí significa que el gasto
   real de esa ruta hay que verlo en la factura del proveedor, no en llm-observatory.
2. **Sin tope de coste duro** (heredado de ADR-0007: el observatory alerta por Discord, no
   bloquea). Sumar proveedores amplía la superficie. Precondición dura si alguna vez el default
   deja de ser Ollama.
3. **`cloud_safe` sigue siendo por fuente**, no un clasificador real de contenido privado. §5 se
   apoya en esa granularidad interina; si la puerta resulta demasiado gruesa para pares de chunks,
   el punto 5 del plan se cae y hay que decirlo en el ADR, no forzarlo.
4. **`max_tokens` obligatorio en Anthropic** (§3.1) mientras el Protocol lo tiene opcional. Elegir
   un default que no trunque síntesis largas del WritingAgent — el único lugar donde la respuesta
   puede ser realmente larga.

## 9. Verificaciones ya hechas

- **2026-09-10** — SDK `llm-observatory` (`packages/sdk-python`): 5 wrappers monitoreados
  (Anthropic/OpenAI/Gemini/Grok/Kimi), `anthropic` como dependencia base, y
  `finalize_metric_pricing` marcando `cost_confidence="unknown"` en modelos fuera de tabla. Esto
  desbloqueó §3.1 y cambió el orden del plan (§7).
- **Pendiente de verificar en vivo**: nada bloqueante. La medición de coste real con un proveedor
  OpenAI-compatible (§2.1) confirma comportamiento ya leído en el código del SDK, no lo descubre.
