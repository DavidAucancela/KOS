"""doc 12 §10.4.5: frontmatter tipado → aristas, sin LLM."""

from __future__ import annotations

from kos_workers.pipeline.structural import BY_FRONTMATTER, frontmatter_edges


def test_frontmatter_edges_author_y_project() -> None:
    edges = frontmatter_edges({"project": "KOS Platform"}, author="David Aucancela")
    kinds = {(e.relation_type, e.target_node_type, e.target_name) for e in edges}
    assert kinds == {
        ("AUTHORED_BY", "Person", "David Aucancela"),
        ("PART_OF", "Project", "KOS Platform"),
    }
    assert all(e.extracted_by == BY_FRONTMATTER for e in edges)


def test_frontmatter_edges_listas_y_sinonimos_en_espanol() -> None:
    edges = frontmatter_edges({"autores": ["Ana", "Beto"], "proyecto": "X"}, author=None)
    names = sorted((e.relation_type, e.target_name) for e in edges)
    assert names == [("AUTHORED_BY", "Ana"), ("AUTHORED_BY", "Beto"), ("PART_OF", "X")]


def test_frontmatter_edges_deduplica_y_tolera_vacio() -> None:
    assert frontmatter_edges(None, None) == []
    assert frontmatter_edges({"author": "  "}, author="") == []
    edges = frontmatter_edges({"author": "Ana"}, author="Ana")  # misma persona 2 vías
    assert len(edges) == 1
