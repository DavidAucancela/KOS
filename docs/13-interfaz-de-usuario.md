# 13 — Interfaz de usuario

**Estado:** 🟡 Borrador, implementado · **Última actualización:** 2026-08-27 · **Habilita:**
mejora sobre la UI ya habilitada por [01 — Arquitectura general](01-arquitectura-general.md)
(dominio 10) y [10 — Estructura del proyecto](10-estructura-del-proyecto.md) §4

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
