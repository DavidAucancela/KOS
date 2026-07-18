from kos_core.ontology import (
    NODE_TYPES,
    RELATION_TYPES,
    canonicalize,
    is_valid_node_type,
    is_valid_relation_type,
)


def test_nueve_tipos_de_nodo() -> None:
    assert {
        "Person",
        "Project",
        "Technology",
        "Concept",
        "Document",
        "Task",
        "Organization",
        "Event",
        "Skill",
    } == NODE_TYPES


def test_diez_tipos_de_relacion() -> None:
    assert len(RELATION_TYPES) == 10
    assert "CONTRADICTS" in RELATION_TYPES  # declarada aunque no se use hasta Fase 5


def test_is_valid_node_type() -> None:
    assert is_valid_node_type("Technology")
    assert not is_valid_node_type("Widget")


def test_is_valid_relation_type() -> None:
    assert is_valid_relation_type("USES")
    assert not is_valid_relation_type("LIKES")


def test_canonicalize_normaliza_variantes_al_mismo_nombre() -> None:
    assert canonicalize("FastAPI") == canonicalize("fast-api") == canonicalize("Fast API")
    assert canonicalize("FastAPI") == "fastapi"


def test_canonicalize_quita_acentos() -> None:
    assert canonicalize("Sebastián Ramírez") == "sebastianramirez"
