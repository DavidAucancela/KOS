import uuid

from kos_core.schemas import ParsedDocument
from kos_workers.pipeline.s1_normalize import normalize


def _doc(body: str) -> ParsedDocument:
    return ParsedDocument(doc_id=uuid.uuid4(), title="nota", body=body)


def test_retira_el_frontmatter_inicial() -> None:
    body = "---\ntitle: Hola\ntags: [a]\n---\n\n# Encabezado\n\nTexto."
    result = normalize(_doc(body))
    assert result.body == "# Encabezado\n\nTexto."


def test_normaliza_fines_de_linea_y_lineas_en_blanco() -> None:
    body = "uno\r\ndos\r\n\r\n\r\n\r\ntres\n\n\n\n"
    result = normalize(_doc(body))
    assert result.body == "uno\ndos\n\ntres"


def test_sin_frontmatter_no_toca_el_markdown() -> None:
    body = "# Título\n\n```python\n# esto no es encabezado\n```\n\n- lista"
    result = normalize(_doc(body))
    assert result.body == body


def test_un_separador_horizontal_no_es_frontmatter() -> None:
    body = "Texto inicial\n\n---\n\nMás texto"
    result = normalize(_doc(body))
    assert result.body == body


def test_no_muta_la_entrada() -> None:
    original = _doc("---\na: 1\n---\ncuerpo\r\n")
    snapshot = original.model_copy(deep=True)
    normalize(original)
    assert original == snapshot
