"""Constantes del sistema de confianza, transversal a documentos/grafo/memoria
(doc 04 §5). Viven en `packages/core` porque `storage/neo4j.py` y
`storage/postgres.py` las necesitan para recalcular `confidence` al perder una
fuente, y `apps/workers/pipeline/s9_confidence.py` las reusa para no duplicar
el valor (ADR-0001: el núcleo no depende de `apps/*`, nunca al revés)."""

from __future__ import annotations

# Boost por fuente adicional (doc 02 §4 regla 4): cada nueva mención sube la
# confianza. Mismo valor usado hacia adelante (se suma una fuente) y hacia
# atrás (se recalcula con las que sobreviven, doc 04 §5).
ALIAS_BOOST = 0.05

# Umbral de alerta temprana tras recalcular confidence al perder una fuente
# (doc 04 §5, decidido 2026-08-13): por debajo de esto, candidato a poda o
# revisión — distinto del umbral de auto-poda por decaimiento (doc 02 §4 regla 4).
PRUNE_THRESHOLD = 0.3
