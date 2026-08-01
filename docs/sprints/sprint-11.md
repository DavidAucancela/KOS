# Retro — Sprint 11: "Tombstone → grafo"

**Estado:** ✅ Cerrado 2026-07-31. Fuera de plan (deuda arrastrada desde Sprint 6, reafirmada en
las retros de Sprint 9 y 10): "tombstone de documentos borrados no propagado al grafo".

## Motivación

Doc 05 §5 ya prometía el comportamiento desde Sprint 5 ("su evidencia se retira del grafo") y
doc 06 §3 ya listaba `document.deleted` con "Grafo" como consumidor — pero nunca se conectó nada.
Tumbar un documento (borrarlo de la fuente) dejaba sus entidades y relaciones extraídas viviendo
para siempre en Neo4j, sin importar que la evidencia que las sustentaba ya no existiera.

## Qué se construye

- **`neo4j_storage.retire_document(driver, doc_id)`** (`packages/core`): saca `doc_id` de
  `sources[]` de nodos y relaciones que lo mencionan; borra los que quedan sin ninguna fuente —
  salvo que estén `locked` (corrección manual, doc 02 §4 regla 5), que sobreviven con `sources`
  vacío porque el usuario ya los validó y no dependen de que un documento los respalde. Relaciones
  primero, nodos después (un nodo sin evidencia no puede quedar con relaciones colgando, aunque
  esas relaciones tuvieran otras fuentes propias — caso límite documentado, no resuelto).
- **`retire_documents` (Postgres) ahora devuelve los `doc_id`** retirados, no solo la cantidad —
  necesario para propagarlos uno por uno al grafo.
- **`kos.graph_retire_document`** (nueva task en `apps/workers`, contraparte de `kos.graph_sync`):
  encadenada directamente desde `kos.sync_source` cuando `_retire_missing` encuentra documentos
  ausentes — mismo patrón de `.delay()` directo que `embed_document`/`graph_sync` (doc 06 ya
  aclara que estos contratos corren como pipeline fijo, no como agentes reales, hasta Fase 4).
- **`document.deleted` ahora se publica de verdad** (antes el schema `DocumentDeleted` existía
  sin ningún emisor ni consumidor) — vía `kos.sync_source`, uno por documento retirado.

## Qué se recorta (deuda visible)

- **Recálculo de `confidence` en lo que sobrevive** (doc 04 §5: "fuente eliminada → recálculo con
  la evidencia restante"): no implementado. No hay una fórmula definida de cuánto debería bajar la
  confianza de un nodo que pierde una de varias fuentes — el modelo actual guarda confianza
  agregada, no una contribución por fuente. Se resuelve el caso principal (evidencia huérfana
  desaparece); el ajuste fino de confianza queda para cuando exista el sistema de confianza real
  de v0.4.
- El caso límite de una relación que sobrevive por fuentes propias pero pierde un extremo (nodo
  borrado por quedar sin evidencia): se lleva la relación igual (`DETACH DELETE`). No visto en la
  práctica; documentado en el docstring de `_retire_document_nodes`.

## Qué se aprendió

- El propio `git grep` del schema (`DocumentDeleted`) encontró la deuda más rápido que leer las
  retros: un evento definido en `kos_core/schemas/events.py` sin un solo emisor ni consumidor en
  todo el repo es la señal más barata de "esto quedó pendiente" — vale la pena como chequeo
  rápido antes de abrir un sprint nuevo sobre deuda vieja.
- Verificar contra infra real encontró un problema operativo, no de lógica: Celery no recarga
  código con `--reload` (a diferencia de uvicorn); una task nueva agregada a `include=[]` no
  existe para un worker que ya está corriendo hasta reiniciarlo. En macOS además `SIGHUP` no sirve
  para reiniciar el worker en caliente ("unstable on this platform") — hay que matar el proceso y
  levantarlo de nuevo. Anotado para no perder tiempo la próxima vez que una task nueva devuelva
  `KeyError` en el worker.
