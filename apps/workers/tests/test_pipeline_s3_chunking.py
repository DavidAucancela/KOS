import uuid

from kos_core.schemas import ParsedDocument
from kos_workers.pipeline.s3_chunking import MAX_CHUNK_CHARS, chunk_by_headings


def _doc(body: str) -> ParsedDocument:
    return ParsedDocument(doc_id=uuid.uuid4(), title="nota", body=body)


def test_divide_por_encabezados_con_preambulo() -> None:
    body = "Preámbulo del documento.\n\n# Uno\n\nContenido de uno.\n\n## Dos\n\nContenido de dos."
    result = chunk_by_headings(_doc(body))

    assert [c.metadata["heading"] for c in result.chunks] == [None, "Uno", "Dos"]
    assert [c.metadata["level"] for c in result.chunks] == [None, 1, 2]
    assert [c.position.order for c in result.chunks] == [0, 1, 2]
    assert result.chunks[0].text == "Preámbulo del documento."
    assert result.chunks[1].text == "Contenido de uno."


def test_offsets_reales_sobre_el_body() -> None:
    body = "intro\n\n# Sección\n\npárrafo uno\n\npárrafo dos"
    result = chunk_by_headings(_doc(body))
    for chunk in result.chunks:
        assert body[chunk.position.start : chunk.position.end] == chunk.text


def test_encabezado_dentro_de_codigo_no_divide() -> None:
    body = "# Real\n\n```python\n# comentario, no encabezado\nx = 1\n```\n\nfin"
    result = chunk_by_headings(_doc(body))
    assert len(result.chunks) == 1
    assert result.chunks[0].metadata["heading"] == "Real"
    assert "# comentario" in result.chunks[0].text


def test_el_texto_no_incluye_la_linea_del_encabezado() -> None:
    body = "# Título\n\nContenido."
    result = chunk_by_headings(_doc(body))
    assert result.chunks[0].text == "Contenido."


def test_seccion_larga_se_subdivide_por_parrafos() -> None:
    parrafo = "palabra " * 100  # ~800 chars
    body = f"# Larga\n\n{parrafo.strip()}\n\n{parrafo.strip()}\n\n{parrafo.strip()}"
    result = chunk_by_headings(_doc(body))

    assert len(result.chunks) > 1
    for chunk in result.chunks:
        assert len(chunk.text) <= MAX_CHUNK_CHARS
        assert chunk.metadata["heading"] == "Larga"
        assert body[chunk.position.start : chunk.position.end] == chunk.text


def test_parrafo_gigante_se_parte_por_longitud() -> None:
    body = "# Gigante\n\n" + "x" * (MAX_CHUNK_CHARS * 2 + 100)
    result = chunk_by_headings(_doc(body))
    assert len(result.chunks) == 3
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in result.chunks)


def test_secciones_vacias_se_ignoran() -> None:
    body = "# Vacía\n\n# Con texto\n\nhola"
    result = chunk_by_headings(_doc(body))
    assert [c.metadata["heading"] for c in result.chunks] == ["Con texto"]


def test_body_vacio_produce_cero_chunks() -> None:
    assert chunk_by_headings(_doc("")).chunks == []
    assert chunk_by_headings(_doc("   \n  ")).chunks == []


def test_no_muta_la_entrada() -> None:
    original = _doc("# A\n\ntexto")
    snapshot = original.model_copy(deep=True)
    chunk_by_headings(original)
    assert original == snapshot
