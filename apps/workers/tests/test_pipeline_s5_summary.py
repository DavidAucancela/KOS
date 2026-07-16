import uuid

from kos_core.schemas import ParsedDocument
from kos_workers.pipeline.s5_summary import build_summary_prompt, make_summary_stage


def _doc(body: str | None) -> ParsedDocument:
    return ParsedDocument(doc_id=uuid.uuid4(), title="t", body=body)


def test_rellena_summary_con_generate() -> None:
    stage = make_summary_stage(lambda prompt: "  Un resumen fiel.  ")
    out = stage(_doc("Contenido del documento sobre Docker."))
    assert out.summary == "Un resumen fiel."


def test_body_vacio_no_llama_a_generate() -> None:
    def generate(prompt: str) -> str:
        raise AssertionError("no debe llamarse con body vacío")

    stage = make_summary_stage(generate)
    assert stage(_doc("   ")).summary is None
    assert stage(_doc(None)).summary is None


def test_respeta_max_chars_de_contexto() -> None:
    captured: list[str] = []

    def generate(prompt: str) -> str:
        captured.append(prompt)
        return "ok"

    body = "x" * 1000
    make_summary_stage(generate, max_chars=10)(_doc(body))
    # el contexto se recorta a max_chars*4 caracteres del body
    assert "x" * 40 in captured[0]
    assert "x" * 41 not in captured[0]


def test_no_muta_la_entrada() -> None:
    doc = _doc("Contenido.")
    make_summary_stage(lambda prompt: "r")(doc)
    assert doc.summary is None


def test_build_prompt_none_si_vacio() -> None:
    assert build_summary_prompt("   ") is None
    assert build_summary_prompt("hola") is not None
