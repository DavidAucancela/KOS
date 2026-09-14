# 13 — Interfaz de usuario

**Estado:** 🟡 Borrador, parcialmente implementado · **Última actualización:** 2026-09-13 ·
**Habilita:** mejora sobre la UI ya habilitada por
[01 — Arquitectura general](01-arquitectura-general.md) (dominio 10) y
[10 — Estructura del proyecto](10-estructura-del-proyecto.md) §4

> Primer documento de diseño dedicado al frontend. Hasta ahora la UI vivía solo como
> [dominio 10 de doc 01](01-arquitectura-general.md) ("interfaz tipo IDE") y el contrato de
> carpetas de [doc 10 §4](10-estructura-del-proyecto.md); cada decisión real (layout de una sola
> pasada del grafo, ausencia de pantalla de memoria, superficie mínima del recomendador) quedó
> dispersa en retros de sprint y en [deuda-tecnica.md](deuda-tecnica.md). Este doc las consolida y
> especifica los tres frentes abiertos de la sección "UI/UX" de esa deuda. No cambia el stack ni
> el layout de cuatro zonas.
>
> **Construido el 2026-08-27** (los tres frentes de §7, sin sprint numerado — trabajo de deuda):
> colapso + persistencia de paneles (`src/lib/uiPrefs.ts`, `App.tsx`, `ChatPage`/
> `ConversationSidebar`), vista de memoria (`src/features/memory/`), y grafo con reacomodo animado
> + resaltado de caminos (`GraphCanvas.tsx`/`GraphPage.tsx`/`useGraph.ts`). El atajo de teclado de
> §3.4 quedó **diferido** a propósito (sin `keydown` global todavía). `src/api/schema.d.ts` se
> regeneró en el camino: estaba desactualizado y no traía `MemoryOut.locked` ni el `PATCH
> `/v1/memory/{id}` (mismo tipo de drift que la fila `PlanOut.post` de la deuda). Este doc sigue
> siendo la fuente de verdad del diseño — cambios de comportamiento requieren PR sobre él primero.
>
> **§8–§11 son diseño nuevo (2026-09-13), sin construir todavía.** Antes de armar wireframes se
> identificaron cuatro huecos que ninguna de las secciones anteriores cubre: el rail no refleja
> problemas de conexión más allá del contador de recomendaciones, no hay ningún canal de mensajes
> transitorios (toasts) ni un patrón único de estado vacío/error, las escrituras al vault
> (`obsidian.*`, doc 06 §4) no tienen ninguna superficie en `apps/web` pese a que `update_note`
> sobrescribe sin pedir nada, y `GET/POST /v1/sources` (doc 06 §3, existe desde Fase 1) no tiene
> ninguna pantalla — hoy sincronizar una fuente solo se puede hacer por API a mano. Selección de
> proveedor LLM y gestión de API keys quedan **fuera de alcance**: son configuración por variable
> de entorno (ADR-0006/0007, doc 15) o del propio navegador (ADR-0010), no hay endpoint que una UI
> pueda leer o escribir todavía.
> /v1/memory/{id}` (mismo tipo de drift que la fila `PlanOut.post` de la deuda). Este doc sigue
> siendo la fuente de verdad del diseño — cambios de comportamiento requieren PR sobre él primero.

## 1. Principio

**Interfaz tipo IDE, no tipo ChatGPT** (doc 01, dominio 10). El conocimiento y el proceso son tan
visibles como la respuesta: el usuario ve qué fuentes hay, qué plan ejecutó el sistema y sobre qué
evidencia respondió. Cuatro zonas:

| Zona | Contenido | Estado |
|---|---|---|
| Izquierda | Explorador de conocimiento (fuentes, entidades, colecciones) + navegación entre vistas | Rail de vistas construido; explorador de fuentes/entidades pendiente |
| Centro | Conversación con planes de ejecución visibles | Construido (`features/chat`) |
| Derecha | Grafo interactivo contextual | Construido como vista propia (`features/graph`), aún no acoplado a la conversación |
| Abajo | Herramientas, trazas y logs de agentes | Construido como vista propia (`features/traces`) |

Reglas transversales:

- **La UI solo habla con la API** (doc 01): nunca con Postgres/Neo4j/Redis directamente. Todo dato
  de dominio entra por `src/lib/api.ts` con tipos generados de OpenAPI (`src/api/schema.d.ts`).
- **Una `feature/` no importa de otra `feature/`** (doc 10 §4): lo compartido baja a
  `src/components/` o `src/lib/`.
- **`src/api/` es generado** — nunca se edita a mano.
- **Librerías chicas de un solo propósito antes que frameworks pesados.** Precedente del Sprint 10:
  el grafo usa `d3-force` para la física y SVG controlado por React para el render, en vez de
  react-flow / cytoscape; zoom y pan se hicieron a mano sobre el `viewBox` del SVG en vez de traer
  `d3-zoom`. Cualquier frente nuevo mantiene ese criterio.

## 2. Estado actual (implementado)

Inventario honesto de lo que existe hoy en `apps/web`, para que las secciones siguientes no
describan un ideal:

- **Stack:** Vite 7 + React 19 + TypeScript, Tailwind v4 (configurado en `src/index.css`, sin
  `tailwind.config`), primitivas estilo shadcn/ui en `src/components/ui/`, íconos `lucide-react`,
  tests con Vitest. Sin router (el cambio de vista es `useState` en `App.tsx`). Sin librería de
  estado global: `useState` local + un hook por feature (`useGraph`, `useChat`,
  `useRecommendations`…) que devuelve `{ data, loading, error, actions }`.
- **Shell (`src/App.tsx`):** rail de íconos `<nav class="w-14">` **siempre visible** con cinco
  vistas — Chat, Grafo, Trazas (Sprint 19), Estado, Métricas (doc 06 §2 addendum 2026-08-21). El
  ícono "Estado" lleva un badge con el conteo de recomendaciones `pending` (mejora posterior a
  Sprint 25).
- **Chat (`features/chat`):** `ChatPage` con `ConversationSidebar` (`<aside class="hidden w-64
  … lg:flex">`, `ConversationSidebar.tsx:105`) y un `CitationViewer` a la derecha (`<div
  class="hidden w-96 … lg:block">`, `ChatPage.tsx:322`). Ambos paneles **se ocultan bajo el
  breakpoint `lg` con Tailwind puro** — no hay control de usuario.
- **Grafo (`features/graph/GraphCanvas.tsx`):** layout de fuerzas calculado **una sola vez por
  cambio de datos** (300 ticks síncronos, `simulation.stop()` + loop, sin simulación corriendo en
  vivo). Render SVG controlado por React. Interacciones a mano: zoom (rueda, listener `wheel`
  pasivo-false), pan (arrastre del fondo), arrastre de nodos (`pointer` events + `setPointerCapture`),
  selección (click / Enter-Space). Botón "Restablecer vista". `GraphPage` tiene un toggle
  "Grafo / Tabla".
- **Métricas (`features/metrics`):** `AgentLatencyBars` (promedio de `cost.ms` por agente,
  2026-08-27).
- **No existía (antes del 2026-08-27):** ninguna pantalla de memoria; ningún uso de `localStorage`
  en todo `apps/web`; ninguna infraestructura de atajos de teclado globales (solo dos `onKeyDown`
  locales). §3–§5 cambiaron los dos primeros; los atajos siguen sin construirse (§3.4).

## 3. Colapso y persistencia de paneles laterales

Frente nuevo (no es deuda previa). Objetivo: que el usuario pueda recuperar ancho horizontal
ocultando barras que no está usando, y que esa elección sobreviva a la recarga.

### 3.1 Qué se puede colapsar

Dos controles **independientes**:

1. **Rail de vistas** (`<nav>` de `App.tsx`, global a toda la app). Colapsado **no desaparece**:
   deja una franja mínima con un único botón de expandir, para no perder nunca la navegación
   entre vistas. Alternativa a evaluar en revisión: colapsar a íconos sin labels ya es el estado
   actual (`w-14`), así que "colapsar" acá significa esconder el rail entero salvo el botón.
2. **Sidebar de conversaciones** del chat (`ConversationSidebar`, local a `ChatPage`). Colapsado
   libera todo el ancho para la conversación y las citas.

Fuera de alcance de esta iteración: colapsar el `CitationViewer` derecho (mismo patrón, se puede
sumar después sin rediseño) y colapsar el panel inferior de trazas (hoy es vista propia, no panel).

### 3.2 Dónde vive el estado

- Rail: `useState` en `App.tsx` (`railCollapsed`).
- Sidebar de chat: `useState` en `ChatPage` (`chatSidebarCollapsed`) — **no** se sube a `App.tsx`
  ni se comparte, respetando "una feature no importa de otra". `ChatPage` ya es dueño de ese
  layout.

Cada `useState` inicializa su valor leyendo de `localStorage` y escribe en cada cambio.

### 3.3 `localStorage` como precedente nuevo

Hoy `apps/web` no usa `localStorage` en ningún lado. Se introduce acotado a **preferencias de
presentación del usuario, nunca datos de dominio** (esos siempre vienen de la API — regla de
doc 01). Concretamente:

- Un helper mínimo en `src/lib/uiPrefs.ts` (stateless, cae bajo la regla de doc 10 §4): `get<T>(key,
  fallback)` / `set<T>(key, value)`, tipados, envueltos en `try/catch` para tolerar modo incógnito
  o storage deshabilitado (devuelve el fallback, no rompe).
- Claves con namespace: `kos.ui.railCollapsed`, `kos.ui.chatSidebarCollapsed`.
- El doc deja explícito que este helper **no** es un mecanismo de caché de datos de API ni de
  estado de dominio. Si más adelante aparece la necesidad de persistir algo que no sea una
  preferencia de presentación, eso es una decisión nueva.
- **Candidato a ADR:** si en revisión se considera que "adoptar `localStorage` para preferencias
  de UI" es una decisión estructural (y no un detalle de implementación), se registra como ADR
  antes de construir. Es la primera dependencia del navegador como almacén en el proyecto.

### 3.4 Interacción

- Botón visible de colapsar / expandir en cada barra, con `aria-expanded` y `aria-label`. Íconos
  `PanelLeftClose` / `PanelLeftOpen` de `lucide-react` (ya disponible, sin dependencia nueva).
- **Atajo de teclado — diferido (2026-08-27).** Un atajo (p. ej. `[` para el rail) introduciría el
  primer `window.addEventListener("keydown")` global del proyecto. Se construyeron solo los
  botones; el atajo queda para una segunda iteración. Si se retoma, va en un `useEffect` de
  `App.tsx` con su cleanup, ignorando el evento cuando el foco está en un `input` / `textarea`.

### 3.5 Responsive

El override actual `hidden lg:flex` / `hidden lg:block` de los paneles del chat se reemplaza por la
lógica de colapso: **por defecto colapsado bajo `lg`**, expandido a partir de `lg`, pero una
elección explícita del usuario (valor en `localStorage`) gana sobre el breakpoint en ambos
sentidos. El rail hoy no tiene override responsive; su default es expandido en cualquier ancho.

## 4. Auditoría de memoria en la UI

Retoma la deuda de [Sprint 12](sprints/sprint-12.md), reafirmada en
[Sprint 15](sprints/sprint-15.md) (decisión explícita del usuario 2026-08-15 de dejarla fuera del
cierre de v0.4): `apps/web` no tiene pantalla de memoria, a diferencia del grafo desde Sprint 10.

### 4.1 Alcance

Nueva `feature/` `src/features/memory/` con **vista propia en el rail** (sexto ícono), igual que
Grafo (Sprint 10) y Trazas (Sprint 19) se sumaron como vistas nuevas. Alcance mínimo:

- **Listar** items de memoria: `content`, `type` (episódica / semántica…), `confidence`,
  `salience`, `sources[]`, `created_at` / `last_accessed_at`, y las marcas `locked`,
  `archived_at`, `superseded_by`, `prune_candidate`.
- **Filtrar** por `type` y búsqueda de texto (`q`), con paginación por cursor.
- **Corregir manualmente** un item: fijar `content` / `type` / `confidence`, lo que además lo
  marca `locked` (deja de recalcularse su `confidence` y de entrar a la consolidación) — análogo
  a la corrección de nodos del grafo de Sprint 9.
- **Archivar** un item.

Cada ítem muestra el contenido recortado a 3 líneas (`line-clamp-3`) con "Ver más / Ver menos"
cuando es largo, para que la lista sea escaneable. Al construir esto se corrigió además un bug
latente de `PageContainer` (`src/components/page.tsx`): usaba `min-h-screen` dentro de la zona de
contenido de `App.tsx` (alto fijo + `overflow-hidden`), así que cualquier pantalla larga se
recortaba **sin barra de scroll** — ahora es `h-full overflow-y-auto` (beneficia también a
Métricas / Estado / Grafo).

Fuera de alcance: edición libre en lote, visualización de la consolidación episódica→semántica,
timeline de decaimiento. Se suman si aparece el caso de uso.

### 4.2 API — ya existe, sin endpoints nuevos

`apps/api/src/kos_api/routes/memory.py` (doc 06 §2, doc 04 §5):

| Método | Ruta | Uso en la UI |
|---|---|---|
| `GET` | `/v1/memory?type=&q=&cursor=&limit=` → `MemoryPage {items, next_cursor}` | listado + filtros + paginación |
| `PATCH` | `/v1/memory/{id}` (`content?`, `type?`, `confidence?`) → `MemoryOut` | corrección manual (fija `locked`, migración `0014`) |
| `DELETE` | `/v1/memory/{id}` → 204 | archivar |

La UI no necesita nada del backend. `src/api/schema.d.ts` se regeneró al construir esto: estaba
desactualizado y no traía `MemoryOut.locked` ni la operación `PATCH /v1/memory/{id}` (mismo drift
que la fila `PlanOut.post` de la deuda). Se generó `app.openapi()` a un archivo y se corrió
`openapi-typescript` contra él (sin necesitar la API levantada).

### 4.3 Patrón

Hook `useMemory` (`src/features/memory/useMemory.ts`) devolviendo `{ items, nextCursor, loading,
error, filters, applyFilters, loadMore, mutating, mutationError, correct, archive }`, mismo molde
que `useGraph` / `useRecommendations`. `MemoryPage.tsx` usa `PageContainer`/`PageHeader` y un
`MemoryRow` con formulario de corrección inline (espejo de `NeighborRow` en `GraphPage`). Nada
compartido sube fuera de `features/memory/`.

## 5. Grafo: animación de layout y resaltado de caminos

Retoma la deuda de [Sprint 10](sprints/sprint-10.md). El zoom/pan de esa misma fila ya se resolvió
(2026-08-18, ver "Resuelta" en [deuda-tecnica.md](deuda-tecnica.md)); quedan dos sub-ítems.

### 5.1 Animación de layout — Opción A (elegida 2026-08-27)

Sprint 10 decidió **a propósito** que el layout se calcula una sola vez y se muestra estático (más
arrastre manual): así no compite con el arrastre del usuario y alcanza para el volumen actual
(`limit` de ~20 nodos). Esta iteración **no la revierte**: implementa la **Opción A — reacomodo
animado acotado**.

- La pasada síncrona de 300 ticks se mantiene para la **primera carga** (no hay nada desde donde
  animar) y para `prefers-reduced-motion`.
- Cuando llegan datos nuevos y **ya había un layout en pantalla** (re-fetch tras `graph.updated` o
  una corrección), la simulación se reanima desde las posiciones actuales: `alpha(0.6)` +
  `alphaDecay(0.05)`, 3 ticks por frame vía `requestAnimationFrame`, y **se detiene sola** cuando
  `alpha() <= alphaMin()`. Nunca queda una simulación corriendo en reposo.
- Los nodos que el usuario arrastró se registran en `pinnedRef` y se fijan (`fx`/`fy`) al recrear
  la simulación, para que la animación no se los mueva.
- El `useEffect` limpia el `requestAnimationFrame` y llama `simulation.stop()` al desmontar o
  antes del siguiente cambio de datos.

### 5.2 Resaltado de caminos — construido (2026-08-27)

`GET /v1/graph/path` existe desde Sprint 9. Se construyó la interacción mínima:

- Botón **"Resaltar camino"** en la barra de `GraphPage` (solo en vista de grafo). Al activarlo,
  clickear un nodo no abre su vecindario: fija el **origen** (marcado con un anillo punteado);
  el siguiente click fija el **destino** y dispara `GET /v1/graph/path?from_id=&to_id=`.
- El camino devuelto se resalta (`highlightNodeIds` / `highlightRelationIds` pasados a
  `GraphCanvas`): nodos y aristas del camino en color `--primary`, todo lo demás atenuado
  (`opacity` 0.2 / 0.12). Un enlace **"Limpiar"** quita el resaltado; el estado vive en
  `useGraph` (`path` / `findPath` / `clearPath`).
- 404 ("no hay camino") se muestra como texto, no rompe la vista.

### 5.3 Restricción de implementación

El cambio queda contenido en `src/features/graph/` (`GraphCanvas.tsx`, `GraphPage.tsx`,
`useGraph.ts`, `types.ts`). Se mantiene la convención del Sprint 10: no traer `d3-zoom` /
`d3-drag` / react-flow — solo `d3-force` para la física.

## 6. Riesgos y no-objetivos

- **No** se rediseña el layout de cuatro zonas ni se cambia el stack (Vite / React / Tailwind v4 /
  shadcn).
- `localStorage` se usa **solo** para preferencias de presentación; nunca para datos de dominio ni
  como caché de respuestas de API.
- La animación de layout del grafo **no** debe dejar una simulación corriendo en reposo
  (regresión sobre la decisión del Sprint 10) — se cumple: `requestAnimationFrame` se corta en
  `alpha() <= alphaMin()`.

## 7. Evolución por fases

Estos son ítems de **deuda de UI**, no de v1.1 (Plataforma) — la regla 1 del roadmap (doc 07) que
congela la planificación de v1.1 hasta cerrar el criterio de salida de v1.0 no aplica acá.

Los tres frentes se construyeron juntos el **2026-08-27** (trabajo de deuda, sin sprint numerado),
en este orden de aislamiento:

| Orden | Frente | Estado | Archivos |
|---|---|---|---|
| 1 | Colapso + persistencia de paneles (§3) | ✅ construido | `src/lib/uiPrefs.ts`, `App.tsx`, `features/chat/ChatPage.tsx` + `ConversationSidebar.tsx` |
| 2 | Vista de auditoría de memoria (§4) | ✅ construido | `src/features/memory/` (`types.ts`, `useMemory.ts`, `MemoryPage.tsx`), entrada en `App.tsx` |
| 3 | Grafo: animación (§5.1) + resaltado de caminos (§5.2) | ✅ construido | `src/features/graph/` (`GraphCanvas.tsx`, `GraphPage.tsx`, `useGraph.ts`, `types.ts`) |

Verificación: `tsc -b`, `eslint .` y `vite build` limpios; `vitest` 52/52 (16 tests nuevos —
`uiPrefs.test.ts`, `MemoryPage.test.tsx`, y casos sumados a `App`/`GraphCanvas`/`GraphPage`). El
polyfill de `localStorage` para jsdom se agregó en `tests/setup.ts` (esta config de jsdom no lo
expone). Las tres filas de "UI/UX" de [deuda-tecnica.md](deuda-tecnica.md) pasan a "Resuelta"
(2026-08-27, sin sprint numerado).

## 8. Rail: aviso de conexión degradada

**Estado: diseño, sin construir.** Decisión explícita al discutirlo (2026-09-13): **no se agrega
un ícono nuevo de "estado de conexión"** en el rail. `App.tsx` ya reserva ese rol al ícono
**Estado**, que hoy solo cuenta recomendaciones `pending` (badge numérico). Partir la señal en dos
íconos (uno para recomendaciones, otro para salud de servicios) fragmentaría algo que ya tiene un
lugar — la vista `StatusPage` — y contradice el criterio de doc 13 de no sumar superficie nueva
sin necesidad.

### 8.1 Qué cambia

- El badge del ícono **Estado** (`App.tsx`) pasa a reflejar **dos señales, con prioridad**: si
  `useHealth()` devuelve `status === "degraded"` o hay `error` (API inaccesible), el badge se
  pinta con la variante `destructive` y listo — no importa si además hay recomendaciones
  pendientes, un servicio caído es más urgente que una recomendación. Si no hay problema de salud,
  el badge vuelve al comportamiento actual (conteo de `pending`).
- **`App.tsx` gana `useHealth()`** además de `useRecommendations()`. Es el mismo hook que ya usa
  `StatusPage` (`features/status/useHealth.ts`, polling cada 5 s) — sin lógica nueva, solo un
  segundo consumidor. Encaja con la regla de doc 10 §4 (una `feature/` no importa de otra): el
  hook ya vive en `features/status/`, que es justamente el dueño del concepto "salud del sistema";
  `App.tsx` no es una feature, así que consumir el hook desde el shell no la viola.
- `aria-label` del ícono Estado distingue los casos: `"Estado (servicio degradado)"` pesa más que
  `"Estado (N recomendaciones pendientes)"`.

### 8.2 Fuera de alcance

- No se agrega un tooltip con el detalle de qué servicio falló — para eso ya está `StatusPage`, a
  un click de distancia. El badge es solo una señal de "andá a mirar", no un resumen.
- `useRecommendations()` en `App.tsx` sigue sin polling propio por ahora (ver §9.4, que sí lo
  necesita para los toasts) — este frente no lo cambia.

## 9. Sistema de mensajes

**Estado: diseño, sin construir.** Hoy cada `feature/` resuelve loading/error/vacío por su cuenta
dentro de su propio hook (`{ data, loading, error }`, patrón ya establecido) y los renderiza a
mano (ver el banner de error de `StatusPage.tsx` o el `line-clamp` de `MemoryPage`). Eso está bien
para el dato de dominio de cada pantalla, pero faltan tres piezas transversales que hoy no existen
en ningún lado de `apps/web`.

### 9.1 Toasts (mensajes transitorios)

Mismo criterio que el grafo (doc 13 §1): **librería chica de un solo propósito, no un framework**.
No se trae `sonner` / `react-hot-toast` — se construye a mano, es poco código y evita una
dependencia nueva por una necesidad acotada.

- `src/components/ui/toast.tsx` (nivel `components/ui`, no una feature): un `ToastProvider`
  (Context + `useState<Toast[]>`) montado una sola vez en `App.tsx`, y un `useToast()` que expone
  `push({ title, description?, variant })` con `variant: "default" | "success" | "destructive"`
  (mismas variantes que `Badge`, ya en `components/ui/badge.tsx`, para no inventar una paleta
  nueva).
- Cada toast se autodescarta a los 5 s (`setTimeout` + cleanup) y es descartable a mano con una X.
  Se apilan en una esquina fija (abajo a la derecha) sobre un `<div role="status" aria-live="polite">`
  para que un lector de pantalla los anuncie sin robar el foco.
- **Qué dispara un toast** (lista cerrada, para no convertirlo en el canal de todo): confirmación
  de una acción explícita del usuario que no tiene su propia superficie de resultado (archivar un
  ítem de memoria, aprobar/rechazar una propuesta o recomendación, sincronizar una fuente — §11);
  y el aviso proactivo de una recomendación nueva (§9.4). **No** reemplaza los errores inline de
  cada formulario (ej. validación de un campo) ni el banner de `StatusPage` — esos siguen donde
  están, son parte del contenido de la página, no un evento transitorio.

### 9.2 Estado vacío

`src/components/ui/empty-state.tsx`: `<EmptyState icon={LucideIcon} title description action?>`.
Reemplaza los "sin datos" ad-hoc (hoy `MemoryPage`/`GraphPage`/`RecommendationsPanel` seguramente
difieren entre sí en cómo lo resuelven, si es que lo resuelven). Un solo componente para: vault sin
documentos, memoria vacía, sin recomendaciones, grafo sin nodos, sin conversaciones. Copy siempre
en español, sin jerga técnica ("Todavía no hay memorias" en vez de "0 rows"), con una acción cuando
tiene sentido (ej. desde memoria vacía no hay acción; desde fuentes sin sincronizar, "Sincronizar
ahora" — §11).

### 9.3 Estado de error (pantalla completa de una feature)

`src/components/ui/error-state.tsx`, generalización del banner ya usado en `StatusPage.tsx`
(`border-destructive/30 bg-destructive/10 text-destructive`): `<ErrorState message retry?>`. Se
adopta en las features que hoy renderizan su error a mano, sin cambiar la forma en que cada hook
expone `error` (siguen siendo `string | null`). No es para errores de campo de un formulario — esos
siguen inline, junto al campo.

### 9.4 Avisos proactivos del Recomendador

Hueco real anotado en el propio código: el comentario de `App.tsx` dice que el fetch de
`useRecommendations()` "se hace una vez al montar el shell" — si `RecommenderAgent` genera una
recomendación nueva mientras el usuario ya está en Chat o Grafo, no hay ninguna señal hasta que
recargue o entre a Estado.

- `useRecommendations()` gana **polling** (mismo intervalo que `useHealth`, 5 s es demasiado
  agresivo para algo que se dispara ante `graph.updated`, no ante cada request — se propone 30 s;
  ver riesgos en §9.5).
- El hook recuerda el conjunto de `id` ya vistos (`localStorage`, clave
  `kos.ui.seenRecommendationIds`, mismo mecanismo de `uiPrefs.ts` del §3.3 — sigue siendo
  preferencia de presentación, no dato de dominio: es solo "qué ya vio este navegador"). Cuando el
  polling trae un `id` de status `pending` que no está en ese conjunto, dispara un toast
  ("Nueva recomendación: {título}", acción "Ver" → navega a Estado) y lo agrega al conjunto visto.
- **Candidato a ADR si esto crece**: hoy es polling simple porque el volumen es bajo (un vault
  personal, `RecommenderAgent` no genera en ráfaga). Si más adelante se necesita push real
  (SSE/WebSocket), es una decisión estructural nueva, no una extensión de este diseño.

### 9.5 Riesgos y preguntas abiertas

- Polling de recomendaciones cada 30 s desde cualquier vista (no solo Estado) suma tráfico
  constante a la API incluso sin actividad — aceptable para un solo usuario local, a revisar si
  esto se expone en el despliegue gestionado (doc 14) contra el rate limit de ADR-0010.
- **Pregunta abierta:** ¿el toast de recomendación nueva debe sonar/vibrar o alcanza con el
  aviso visual + el badge del §8? Se propone solo visual por ahora — es la opción menos intrusiva
  y coherente con que `apps/web` no tiene hoy ningún otro sonido o notificación del navegador
  (`Notification` API).

## 10. Confirmación y visibilidad de escrituras al vault

**Estado: diseño, sin construir.** Las tools `obsidian.create_note` / `update_note` /
`create_folder` (doc 06 §4) solo son alcanzables desde comandos explícitos del chat (`/crear-nota`,
etc. — deuda-tecnica.md, fila Sprint 20), nunca desde el catálogo del Planner (regla 7 de
CLAUDE.md). Es decir: **el usuario ya dio su confirmación al escribir el comando** — `confirm=true`
forzado por código en `WritingAgent` no es un bypass de aprobación humana, es la consecuencia de
que la aprobación ya ocurrió al invocar el comando a propósito. Este diseño no reabre esa decisión.

Lo que sí falta es **visibilidad**: hoy `apps/web` no tiene ningún tratamiento especial para el
resultado de estos comandos — probablemente se ven como un mensaje de texto más en la conversación.

### 10.1 `create_note` / `create_folder` — no destructivas

No necesitan confirmación previa (crear algo nuevo no puede pisar datos existentes). Sí necesitan
un **resultado visible y distinto de una respuesta normal**: una tarjeta inline en el hilo del chat
(mismo lugar donde hoy aparece el mensaje del asistente) con ícono de archivo/carpeta, la ruta
creada, y un enlace para abrir la nota (si `apps/web` corre junto al vault local) o al menos
copiar la ruta. Objetivo: que "¿se creó o no?" sea obvio de un vistazo, sin leer el texto entero.

### 10.2 `update_note` — destructiva, sobrescribe sin diff

**Este es el hueco real.** `update_note` es overwrite y exige que la nota ya exista
(deuda-tecnica.md, fila Sprint 20): si el LLM genera un contenido equivocado, el usuario pierde el
contenido anterior de la nota sin aviso ni versión previa a mano (no hay "deshacer" — Obsidian no
es el dueño del historial, doc ADR-0001). Esto es exactamente el tipo de acción "difícil de
revertir" que las reglas de este proyecto piden confirmar antes de ejecutar, no después.

**Decisión (2026-09-13): reusar el patrón `memory_proposals` tal cual, no inventar uno nuevo.**
Es exactamente el mismo problema que ya resolvió Sprint 21 para `memory.store` (LLM propone,
aprobación humana real antes de persistir) — reusar el mecanismo entero (tabla, servicio, rutas,
panel) es menos superficie nueva que la alternativa "armar la confirmación en el frontend con el
contenido de la respuesta del chat", y además dejaba la propuesta persistida, auditable, y
sobreviviendo a un refresh — lo que la alternativa liviana no daba.

**Backend (mirror exacto de `memory_proposals`, doc 06 §4 addendum, migración `0012a`):**

- Tabla `note_update_proposals` (migración nueva, encadenada detrás de la última —`0014` a la
  fecha, doc 04 §5—): `proposal_id` (UUID, PK), `note_path` (texto), `content` (texto, el contenido
  nuevo completo propuesto), `status` (`pending` / `approved` / `rejected`, default `pending`),
  `rejected_reason` (texto, nullable), `trace_id` (texto), `created_at` / `resolved_at`. Mismos
  índices por `status` y `created_at` que `0012a`.
- `kos_core.schemas.note_update_proposals.NoteUpdateProposal` (pydantic), espejo de
  `MemoryProposal`.
- `packages/mcp-tools/.../obsidian.py`: `update_note` gana el mismo desdoblamiento que
  `memory.store` (`kos_mcp/tools/memory.py`) — sin `confirm=True`, no escribe: crea el registro en
  `note_update_proposals` y devuelve el `proposal_id`. `WritingAgent`, al manejar el comando de
  chat, llama a `update_note` **sin** `confirm=True` a propósito (a diferencia de `create_note`,
  que sigue forzando `confirm=True` y escribiendo directo — no es destructiva). El resultado que
  ve el chat es "propuesta creada", no "nota actualizada".
- `apps/api/src/kos_api/routes/notes_proposals.py`: `GET /v1/notes/proposals?status=&cursor=&limit=`
  y `PATCH /v1/notes/proposals/{id}` (`status: "approved" | "rejected"`, `reason?`) — mismas firmas
  que `/v1/memory/proposals`.
- `notes_proposal_service.resolve_proposal`: `approved` llama a `caller.call_tool("obsidian.update_note",
  {note_path, content, confirm: True, trace_id})` — la aprobación humana real, mismo punto donde
  `memory_proposal_service` pasa `confirm=True` para `memory.store` — y guarda el resultado;
  `rejected` solo cierra la propuesta sin tocar el vault.

**Frontend:** `src/features/note-proposals/` (mismo molde que `memory-proposals/`):
`useNoteProposals` (`{ items, loading, error, resolve }`) + `NoteProposalsPanel.tsx`, listado en
`StatusPage.tsx` junto a `MemoryProposalsPanel` (no en el chat — mismo lugar donde ya se aprueban
o rechazan propuestas de memoria, para no duplicar el patrón de revisión en dos sitios distintos).
Cada fila: ruta de la nota, preview del contenido nuevo (`line-clamp-3` + "Ver más", mismo patrón
que `MemoryRow`), botones "Aprobar" / "Rechazar". Al resolver, toast (§9.1) con el resultado.

### 10.3 Fuera de alcance

- Diff visual línea por línea entre el contenido viejo y el nuevo de la nota — un preview del
  contenido nuevo alcanza para la primera iteración; un diff es una mejora, no un bloqueante.
  Se suma si en el uso real la gente pide ver qué cambió, no antes.

## 11. Fuentes conectadas: gestión y sincronización manual

**Estado: diseño, sin construir.** `GET/POST /v1/sources` y `POST /v1/sources/{id}/sync` existen
desde Fase 1 (doc 06 §3) y no tienen ninguna pantalla en `apps/web` — hoy sincronizar una fuente a
mano solo se puede hacer llamando a la API directo. Esto es distinto de "Configuración" en el
sentido amplio (proveedor LLM, API keys): ninguna de esas dos tiene endpoint hoy (env vars /
navegador respectivamente, ver la nota de alcance al inicio del doc), así que no entran en esta
sección ni se inventa una pantalla para algo que no se puede leer ni escribir todavía.

### 11.1 Alcance

Séptima vista del rail, ícono **Fuentes** (no "Configuración" — el nombre debe decir lo que
realmente hace, nada más):

- **Listar** fuentes registradas: tipo (vault / carpeta PDFs / repo, doc 06 §3), ruta, último
  sync, y su flag `cloud_safe` (ADR-0007 — de solo lectura acá, se decide al registrar la fuente,
  no se edita desde esta vista en esta iteración).
- **Sincronizar ahora**: botón por fuente → `POST /v1/sources/{id}/sync`, seguido de polling a
  `GET /v1/ingest/jobs/{id}` (mismo intervalo que `useHealth`) mientras el job esté en curso,
  mostrando su estado (`pending` / `running` / `done` / `error`) inline en la fila de esa fuente.
  Al terminar, un toast (§9.1) con éxito o error — es exactamente el caso "acción explícita sin
  superficie de resultado propia" que justifica el toast.
- **Registrar una fuente nueva** (`POST /v1/sources`): formulario mínimo (tipo, ruta,
  `cloud_safe`). Sin validación de que la ruta exista desde el frontend — eso lo valida la API.

### 11.2 Patrón

Mismo molde que el resto: `src/features/sources/` con `useSources` (`{ items, loading, error,
syncing, sync, register }`) + `SourcesPage.tsx` sobre `PageContainer`/`PageHeader`, tabla de filas
con acción por fila (mismo espejo que `MemoryRow`/`NeighborRow`). Estado vacío (§9.2) para "sin
fuentes registradas todavía", con la acción "Registrar fuente" apuntando al formulario.

### 11.3 Fuera de alcance

- Editar o borrar una fuente registrada — no hay endpoint (`DELETE /v1/sources/{id}` no existe en
  doc 06 §3); se agrega si aparece la necesidad real, no antes.
- Selección de proveedor LLM / modelo por tarea y gestión de API keys de despliegue — confirmado al
  inicio del doc: son configuración por entorno (doc 15) o del navegador (ADR-0010), no hay
  endpoint que esta vista pueda consumir.

## 12. Evolución de este frente

| Sección | Frente | Estado |
|---|---|---|
| §8 | Rail: badge de Estado extendido a salud de servicios | 🟡 diseño |
| §9 | Toasts, estado vacío, estado de error, avisos del Recomendador | 🟡 diseño |
| §10 | Visibilidad de `create_note`/`create_folder`; confirmación de `update_note` vía `note_update_proposals` (mirror de `memory_proposals`) | 🟡 diseño |
| §11 | `features/sources/`: listar, registrar, sincronizar fuentes | 🟡 diseño |

Ninguno de los cuatro cambia el layout de cuatro zonas ni el stack (regla de §1). Las cuatro
secciones ya tienen su forma final (§10.2 se resolvió el 2026-09-13: reusar el patrón
`memory_proposals` completo — tabla, servicio, rutas y panel — en vez de una confirmación armada
en el frontend) y pueden wireframearse tal cual están escritas acá.
