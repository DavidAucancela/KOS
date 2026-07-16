# ADR-0003 — Neo4j como fuente de verdad de las relaciones

**Estado:** Aceptado
**Fecha:** 2026-07-11

## Contexto

El corazón de KOS es un grafo de conocimiento: entidades tipadas y relaciones con evidencia y confianza. Los casos de uso clave son consultas de caminos ("¿qué conecta X con Y?"), vecindarios, y deducciones estructurales ("sabes A, B, C; te falta D") que en SQL serían joins recursivos ilegibles.

## Decisión

**Neo4j** (Community) es la fuente de verdad de entidades y relaciones. Postgres guarda documentos y chunks; el grafo los referencia por `doc_id`/`chunk_id`. La consistencia entre ambos es eventual, reconciliada por el pipeline de aprendizaje.

## Alternativas consideradas

- **Grafo en Postgres (tablas edges/nodes + CTEs recursivas)** — un servicio menos, pero las consultas de caminos/vecindarios se vuelven lentas y crípticas; sin herramientas de visualización nativas. Descartada.
- **Apache AGE (extensión de grafo para Postgres)** — prometedor y mantendría un solo servicio, pero menos maduro, menor ecosistema y tooling. Reevaluable si operar Neo4j pesa demasiado.
- **Memgraph / Kùzu** — interesantes (Kùzu embebido especialmente), pero ecosistema y visualización más limitados. Reevaluables.

## Consecuencias

- Positivas: Cypher expresa los casos de uso de forma natural; Neo4j Browser da visualización gratis desde el día uno; APOC cubre algoritmos de grafos.
- Negativas: dos fuentes de verdad (documentos en PG, relaciones en Neo4j) exigen disciplina de sincronización — mitigado porque el grafo es **reconstruible** desde los documentos (`kos reindex`).
- Licencia Community: sin clustering ni backups en caliente; suficiente para v0.x–v1.0 single-node.
