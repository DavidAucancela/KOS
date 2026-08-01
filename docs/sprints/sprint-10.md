# Retro — Sprint 10: "Visualización del grafo en la UI"

**Estado:** ✅ Cerrado 2026-07-31. Del plan original (doc 08): "Visualización del grafo en la UI",
cierra v0.3 — Knowledge Graph.

## Motivación

Sprint 9 dejó la corrección manual del grafo funcionando pero solo como tabla ("deliberadamente
una tabla, no un grafo dibujado — eso es el Sprint 10", retro de Sprint 9). El caso de uso "¿qué
conecta X con Y?" (criterio de salida de v0.3, doc 07) se entiende mucho mejor mirando el grafo
que leyendo filas.

## Qué se construye

- **Backend — template `subgraph`** (doc 06 §2, `POST /v1/graph/query`): los templates existentes
  no alcanzaban para dibujar un grafo — `most_connected` trae nodos sin relaciones entre ellos,
  y `neighbors_by_type` trae el vecindario completo de *un* nodo (incluye vecinos fuera del
  conjunto mostrado). `subgraph` combina ambos: los nodos más conectados (mismo criterio que
  `most_connected`) más las relaciones activas *entre ellos* — subgrafo inducido, sin Cypher
  libre (`neo4j_storage.subgraph_relations`, parametrizado por lista de ids).
- **Frontend — `GraphCanvas`** (`apps/web/src/features/graph/GraphCanvas.tsx`): layout de fuerzas
  vía `d3-force` (`forceManyBody`/`forceLink`/`forceCenter`/`forceCollide`), calculado una sola
  vez por cambio de datos (300 ticks síncronos, no una simulación corriendo en vivo) y renderizado
  como SVG controlado por React — d3 solo aporta la física, nunca toca el DOM directamente. Nodos
  coloreados por tipo (leyenda visible), radio proporcional al grado, arrastre manual simple
  (sin recalcular el layout completo). Nodos `locked` y el nodo seleccionado se distinguen por
  trazo.
- **`GraphPage`**: toggle "Grafo"/"Tabla" — la tabla de Sprint 9 se conserva intacta (sigue siendo
  más rápida para revisar en detalle), el grafo es la vista por defecto. Ambas comparten el mismo
  `useGraph()` (ahora trae `nodes` + `relations` desde `subgraph` en una sola llamada) y el mismo
  panel de detalle/corrección — clickear un nodo en el canvas dispara el mismo `selectNode` que
  clickear una fila.
- Doc 06 actualizado antes de codear (agrega `subgraph` a la lista de templates seguros), sin ADR
  nuevo (no cambia ninguna decisión estructural, es una plantilla más sobre el mismo mecanismo).

## Hallazgo crítico (probando contra el vault real, no lo atrapaban los mocks)

Otra vez el patrón de Sprint 8/9: clickear un nodo real en el canvas para ver su detalle devolvía
**HTTP 500**. La causa: 19 relaciones del grafo real no tenían `id` (`AUTHORED_BY` ×6, `RELATED_TO`
×4, `DEPENDS_ON` ×4, `PREREQUISITE_OF` ×2, `MENTIONS` ×1, `USES` ×1, `PART_OF` ×1) — el mismo
problema que motivó el backfill de 275 relaciones en Sprint 9, pero un remanente que quedó afuera
de ese backfill (probablemente relaciones creadas por un sync posterior). `GET
/v1/graph/nodes/{id}` no tiene protección: arma un `GraphRelation` Pydantic por cada vecino y
`id` es un campo requerido, así que revienta con `ValidationError` en cuanto un vecino tiene una
de estas relaciones sin id — le pasaba exactamente igual a la tabla de Sprint 9, solo que nadie
lo había disparado clickeando ese nodo puntual todavía.

Arreglado con el mismo mecanismo que Sprint 9 (backfill puntual vía `cypher-shell`, confirmado con
el usuario antes de tocar datos reales): `MATCH ()-[r]->() WHERE r.id IS NULL SET r.id =
randomUUID()`. Verificado en vivo: el nodo que rompía (27 vecinos) carga su detalle completo
después del backfill, en ambas vistas (grafo y tabla).

## Qué se recorta (deuda visible)

- **Sin animación de la simulación**: el layout se calcula una vez y se muestra estático (más
  arrastre manual); no hay una simulación en vivo que reacomode nodos automáticamente al agregar
  uno nuevo. Suficiente para el volumen actual (`limit` de 20 nodos); si el grafo visible crece
  mucho más, un layout incremental sería la siguiente iteración.
- **Sin zoom/pan**: el canvas es de tamaño fijo (800×520 en un viewBox escalable); con más de ~20
  nodos superpuestos se vuelve difícil de leer. No se construyó porque el `limit` actual no lo
  necesita todavía.
- **Sin caminos (`GET /v1/graph/path`) resaltados en el canvas**: el endpoint existe desde
  Sprint 9, pero dibujar un camino específico sobre la visualización queda para cuando haya un
  caso de uso real que lo pida.
- Los hallazgos de deuda de Sprint 9 (herramientas MCP de lectura, consumidores de
  `graph.updated`, tombstone al grafo) siguen sin resolverse — no tocados en este sprint.

## Qué se aprendió

- Tercer sprint seguido (8, 9, 10) donde una prueba manual contra el vault real encuentra un bug
  que 218 tests mockeados no detectan. El patrón ya es predecible: cualquier endpoint de lectura
  del grafo que no haya sido ejercitado contra el nodo específico que tiene el dato corrupto no
  lo va a atrapar hasta que alguien lo clickee. Vale la pena, en algún momento, un chequeo de
  integridad (`id IS NOT NULL` en todas las relaciones) corriendo periódicamente en vez de
  descubrirlo por accidente — anotado como candidato de deuda, no construido ahora porque todavía
  no hay un lugar natural para ese tipo de chequeo (no hay Fase 3/aprendizaje todavía).
- Separar "física" (d3-force, biblioteca chica de un solo propósito) de "render" (SVG vía React)
  evitó traer una dependencia grande (react-flow, cytoscape) para un caso todavía simple —
  consistente con no agregar abstracción antes de necesitarla.
