import uuid
from datetime import date, datetime
from typing import Any

from kos_core.schemas import ParsedDocument
from kos_workers.pipeline.s2_metadata import extract_metadata

_CUERPO_ES = "El conocimiento se conecta en el grafo y las notas se enlazan con el resto."
_CUERPO_EN = "The knowledge graph connects the notes and links them to the rest of it."


def _doc(
    body: str,
    frontmatter: dict[str, Any] | None = None,
    title: str = "archivo",
    keywords: list[str] | None = None,
) -> ParsedDocument:
    return ParsedDocument(
        doc_id=uuid.uuid4(),
        title=title,
        body=body,
        source_metadata={"frontmatter": frontmatter or {}},
        keywords=keywords or [],
    )


def test_titulo_de_frontmatter_gana_al_encabezado() -> None:
    doc = _doc("# Otro título\n\ntexto", frontmatter={"title": "Desde frontmatter"})
    assert extract_metadata(doc).title == "Desde frontmatter"


def test_titulo_del_primer_encabezado_si_no_hay_frontmatter() -> None:
    doc = _doc("intro\n\n## Sección uno\n\ntexto")
    assert extract_metadata(doc).title == "Sección uno"


def test_titulo_conserva_el_del_archivo_sin_senales() -> None:
    doc = _doc("solo texto plano", title="mi-nota")
    assert extract_metadata(doc).title == "mi-nota"


def test_autor_y_fechas_validas() -> None:
    doc = _doc(
        "texto",
        frontmatter={
            "author": "David",
            "created": "2026-07-01T10:00:00",
            "modified": date(2026, 7, 10),
        },
    )
    result = extract_metadata(doc)
    assert result.author == "David"
    assert result.created_at == datetime(2026, 7, 1, 10, 0)
    assert result.modified_at == datetime(2026, 7, 10)


def test_fechas_invalidas_se_ignoran_sin_lanzar() -> None:
    doc = _doc("texto", frontmatter={"created": "ayer por la tarde", "modified": 42})
    result = extract_metadata(doc)
    assert result.created_at is None
    assert result.modified_at is None


def test_idioma_espanol_ingles_y_sin_senal() -> None:
    assert extract_metadata(_doc(_CUERPO_ES)).language == "es"
    assert extract_metadata(_doc(_CUERPO_EN)).language == "en"
    assert extract_metadata(_doc("x1 x2 x3")).language is None


def test_keywords_union_estable_sin_duplicados() -> None:
    doc = _doc(
        "texto",
        frontmatter={"tags": ["#grafo", "kos", "notas"]},
        keywords=["kos", "vault"],
    )
    assert extract_metadata(doc).keywords == ["kos", "vault", "grafo", "notas"]


def test_no_muta_la_entrada() -> None:
    original = _doc(_CUERPO_ES, frontmatter={"title": "T", "tags": ["a"]})
    snapshot = original.model_copy(deep=True)
    extract_metadata(original)
    assert original == snapshot
