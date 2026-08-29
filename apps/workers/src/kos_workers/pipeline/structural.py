"""Aristas estructurales del grafo a partir de campos ya normalizados del
documento (doc 12 §10.4) — wikilinks, tags y frontmatter que el usuario
escribió a mano en el vault. Determinístico, sin LLM.

Este módulo es puro (dict/listas → specs de arista); la orquestación contra
Neo4j/Postgres vive en `tasks/graph_sync.py`. No conoce Obsidian: recibe
`links`/`keywords`/`frontmatter` ya extraídos por el conector y dejados en
`ParsedDocument` (`pipeline/base.py::bootstrap`) — un conector sin wikilinks
entrega listas vacías y solo aportan §10.4.3 y §10.5 (ADR-0001).
"""

from __future__ import annotations

from dataclasses import dataclass

from kos_core.ontology import canonicalize

# Procedencia (propiedad `extracted_by`, doc 02 §3 / doc 12 §10.7) — permite
# auditar y revertir el grafo por origen de la arista.
BY_WIKILINK = "obsidian.wikilink"
BY_NOTE_ENTITY = "obsidian.note-entity"
BY_SHARED_TAG = "obsidian.shared-tag"
BY_FRONTMATTER = "obsidian.frontmatter"

# Confianzas fijas por tipo de señal (doc 12 §10.4): un wikilink es una
# conexión que el usuario escribió a mano; un tag compartido es una señal débil.
WIKILINK_CONFIDENCE = 0.9
NOTE_ENTITY_CONFIDENCE = 0.9
SHARED_TAG_CONFIDENCE = 0.4
FRONTMATTER_CONFIDENCE = 0.9

# frontmatter key (ya en minúscula) → (tipo de relación, tipo de nodo destino).
# El nodo Document es siempre el origen. doc 12 §10.4.5.
_FRONTMATTER_RELATIONS: dict[str, tuple[str, str]] = {
    "author": ("AUTHORED_BY", "Person"),
    "autor": ("AUTHORED_BY", "Person"),
    "authors": ("AUTHORED_BY", "Person"),
    "autores": ("AUTHORED_BY", "Person"),
    "project": ("PART_OF", "Project"),
    "proyecto": ("PART_OF", "Project"),
}


@dataclass(frozen=True)
class EdgeSpec:
    """Una arista a materializar. `target_*` describe el nodo destino; el nodo
    Document del documento en curso es el origen (salvo que `reversed` — no se
    usa hoy, todas salen del Document)."""

    relation_type: str
    target_node_type: str
    target_name: str
    confidence: float
    extracted_by: str


def _as_names(value: object) -> list[str]:
    if isinstance(value, str):
        parts = [value] if "," not in value else value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = [str(v) for v in value]
    else:
        return []
    return [p.strip() for p in parts if p and p.strip()]


def frontmatter_edges(frontmatter: dict[str, object] | None, author: str | None) -> list[EdgeSpec]:
    """Aristas tipadas desde frontmatter (doc 12 §10.4.5). `author` es la
    columna ya extraída por `s2_metadata`; se suma a lo que diga el frontmatter
    crudo por si el conector la pobló desde otra fuente."""
    specs: list[EdgeSpec] = []
    seen: set[tuple[str, str, str]] = set()

    def add(relation_type: str, node_type: str, name: str) -> None:
        canon = canonicalize(name)
        if not canon:
            return
        key = (relation_type, node_type, canon)
        if key in seen:
            return
        seen.add(key)
        specs.append(
            EdgeSpec(
                relation_type=relation_type,
                target_node_type=node_type,
                target_name=name.strip(),
                confidence=FRONTMATTER_CONFIDENCE,
                extracted_by=BY_FRONTMATTER,
            )
        )

    if author:
        add("AUTHORED_BY", "Person", author)
    for raw_key, (relation_type, node_type) in _FRONTMATTER_RELATIONS.items():
        for name in _as_names((frontmatter or {}).get(raw_key)):
            add(relation_type, node_type, name)
    return specs
