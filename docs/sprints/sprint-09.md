# Retro — Sprint 9: "/v1/graph/* + correcciones manuales"

**Estado:** ✅ Cerrado 2026-07-26. Del plan original (doc 08): "`/v1/graph/*` + correcciones
manuales", ampliado con acuerdo del usuario a corrección de relaciones (no solo nodos) y una
pantalla mínima en `apps/web`.

## Motivación

El Sprint 6 construyó el núcleo del grafo pero lo dejó de solo-escritura: sin forma de leerlo por
API ni de corregir los errores reales que ya se habían visto (retro de Sprint 6: "Docker"
clasificado como `Organization` en vez de `Technology`; "KOS"/"Proyecto KOS" no fusionados por el
umbral de similitud). El doc 06 ya prometía el contrato; el doc 02 regla 5 ya prometía "el usuario
siempre gana" — pero nada estaba implementado.

## Qué se construye

- **Lectura del grafo**: `GET /v1/graph/nodes/{id}` (nodo + vecindario), `GET /v1/graph/path`
  (camino más corto vía `shortestPath()`), `POST /v1/graph/query` con 3 plantillas seguras
  (`nodes_by_type`, `neighbors_by_type`, `most_connected`) — sin Cypher libre en ningún punto de
  entrada.
- **Corrección manual de nodos y relaciones**: `PATCH /v1/graph/nodes/{id}` y `PATCH
  /v1/graph/relations/{id}` fijan `extracted_by="user"`, `confidence=1.0` y `locked=true`;
  `DELETE /v1/graph/relations/{id}` es un rechazo (soft delete vía `rejected: true`, no borrado
  físico). El cambio de tipo de nodo mueve la label real vía `apoc.create.setLabels` (APOC ya
  habilitado en el compose desde Sprint 6); el cambio de tipo de relación borra y recrea (Neo4j no
  permite cambiar el tipo de una relación existente), preservando `id` y propiedades.
- **Protección real contra re-sync** (doc 02 §4 regla 5): `merge_node`/`merge_relation` respetan
  `locked`/`rejected` — ver el hallazgo crítico abajo, la protección terminó siendo más profunda
  de lo planeado.
- **Evento `graph.updated`** (doc 06 §3): se emite en cada corrección; sin consumidor todavía
  (Aprendizaje/Recomendador son Fase 3/4) — deuda visible, no trabajo especulativo.
- **Pantalla mínima en `apps/web`** (`GraphPage`, tercera vista junto a Chat/Estado): tabla de
  nodos priorizada por cantidad de relaciones, detalle con vecindario, formularios inline de
  corrección/rechazo. Deliberadamente una tabla, no un grafo dibujado — eso es el Sprint 10.
- Docs actualizados antes de codear: doc 02 (§3.1/§4, `extracted_by`/`locked` en nodos,
  `rejected` en relaciones) y doc 06 (§2, `PATCH`/`DELETE` de relaciones y el shape de
  `POST /v1/graph/query`), sin ADR nuevo (no se agregó ningún tipo de nodo/relación).

## Hallazgo crítico (probando contra el vault real, no lo atrapaban los mocks)

Igual que en Sprint 8 (`AmbiguousParameter`), la prueba manual contra datos reales encontró tres
bugs que los 217 tests mockeados no detectaron:

1. **`extracted_by` `None` en nodos existentes** (creados antes de que este sprint empezara a
   fijarlo `ON CREATE`) rompía la validación Pydantic de `GraphNode`. Arreglado con
   `coalesce(n.extracted_by, 'parser@v1')` en las queries de lectura.
2. **`neo4j.time.DateTime` no es `datetime.datetime`**: Pydantic rechazaba `created_at`/
   `updated_at`/`extracted_at` tal cual los devuelve el driver. Arreglado centralizando la
   conversión (`_normalize_temporals`, recursiva por los mapas anidados de `find_path`) en el
   `__init__` de `NodeRecord`/`RelationRecord`/`NeighborRecord`.
3. **Relaciones sin `id`** (creadas antes de Sprint 9): backfill puntual de 275 relaciones vía
   `cypher-shell` (mismo patrón que el backfill de `doc_type` en Sprint 8), documentado acá en vez
   de silencioso.
4. **El más importante — duplicados al corregir el tipo de un nodo**: `merge_node` hace `MERGE
   (n:{tipo} {canonical_name: ...})`; al corregir el tipo de "Docker Desktop" de `Organization` a
   `Technology` (vía APOC, cambia la label real), un sync posterior que todavía propusiera
   `Organization` ya no coincidía con el patrón — Neo4j creaba un nodo `Organization` duplicado en
   vez de respetar la corrección, exactamente el caso de uso que motivó el sprint. Reproducido en
   vivo contra el vault real, arreglado agregando un chequeo previo por `canonical_name` **sin
   importar la label** que protege únicamente a los nodos `locked` (el resto conserva el
   comportamiento de Sprint 6: mismo `canonical_name`, tipos distintos, coexisten — polisemia).
   Cubierto con un test de integración dedicado
   (`test_update_node_bloquea_duplicado_si_sync_propone_el_tipo_viejo`) contra Neo4j real.

Verificado extremo a extremo contra datos reales: corregí "Docker Desktop" (`Organization` →
`Technology`, el caso exacto de la retro de Sprint 6) vía la API real y la pantalla web real,
confirmé que la corrección persiste, rechacé una relación real y confirmé que desaparece del
vecindario. Los datos de prueba se revirtieron antes de cerrar (el diagnóstico y el fix quedan;
la corrección real de Docker Desktop se dejó porque es una mejora genuina de los datos).

## Qué se recorta (deuda visible)

- **Herramientas MCP de lectura** (`graph.query`/`graph.get_node`/`graph.find_path`, doc 06):
  `packages/mcp-tools` sigue sin código (solo README); no hay consumidor (Fase 4, planner) — se
  documenta, no se construye.
- **Consumidores de `graph.updated`**: se emite, nadie lo escucha (Aprendizaje/Recomendador no
  existen todavía).
- **Tombstone de documentos borrados al grafo** (deuda de Sprint 6): sigue sin resolverse.
- **Visualización real del grafo** (canvas/force-directed): es el objetivo explícito del
  Sprint 10; la pantalla de este sprint es intencionalmente una tabla.
- La protección por `canonical_name` cruzando labels solo cubre nodos `locked`; una relación
  `rejected` cuyos nodos extremos cambian de identidad (fusión futura) no se re-evalúa — caso
  límite no visto en la práctica todavía, anotado para si aparece.

## Qué se aprendió

- La lección de Sprint 8 se repite: **cualquier feature nueva sobre datos reales necesita al
  menos una prueba manual contra el vault real antes de cerrar el sprint**, sin importar cuántos
  tests mockeados pasen. Tres de los cuatro bugs de esta retro (tipos de Neo4j, `extracted_by`
  nulo, relaciones sin `id`) son específicos de datos que ya existían antes del sprint — un
  entorno de test limpio (fixtures, `mini_vault`) nunca los habría expuesto.
- "El usuario siempre gana" (doc 02 regla 5) es más sutil de lo que suena cuando el correo real es
  Neo4j: una corrección de *propiedades* es un `SET` condicional simple, pero una corrección de
  *tipo* cambia la identidad estructural (la label) que el resto del sistema usa para encontrar el
  nodo — la protección tiene que vivir al nivel de "¿existe ya algo con este nombre, sin importar
  qué label tenga?", no solo "¿este campo está bloqueado?".
