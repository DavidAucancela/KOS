import uuid

from kos_core.schemas import ParsedDocument
from kos_workers.pipeline.s7_entities import build_entities_prompt, make_entities_stage


def _doc(body: str | None) -> ParsedDocument:
    return ParsedDocument(doc_id=uuid.uuid4(), title="t", body=body)


def test_rellena_entities_con_generate() -> None:
    respuesta = '[{"name": "FastAPI", "type": "Technology", "confidence": 0.9}]'
    stage = make_entities_stage(lambda prompt: respuesta)
    out = stage(_doc("Usamos FastAPI en el proyecto."))
    assert len(out.entities) == 1
    assert out.entities[0].name == "FastAPI"
    assert out.entities[0].type == "Technology"


def test_body_vacio_no_llama_a_generate() -> None:
    def generate(prompt: str) -> str:
        raise AssertionError("no debe llamarse con body vacío")

    stage = make_entities_stage(generate)
    assert stage(_doc("   ")).entities == []
    assert stage(_doc(None)).entities == []


def test_tipo_invalido_se_descarta() -> None:
    respuesta = '[{"name": "Widget", "type": "NoExiste", "confidence": 0.9}]'
    stage = make_entities_stage(lambda prompt: respuesta)
    assert stage(_doc("texto")).entities == []


def test_json_malformado_no_lanza() -> None:
    stage = make_entities_stage(lambda prompt: "esto no es JSON")
    assert stage(_doc("texto")).entities == []


def test_no_es_lista_se_ignora() -> None:
    stage = make_entities_stage(lambda prompt: '{"name": "FastAPI"}')
    assert stage(_doc("texto")).entities == []


def test_no_muta_la_entrada() -> None:
    doc = _doc("texto")
    make_entities_stage(lambda prompt: '[{"name": "X", "type": "Concept"}]')(doc)
    assert doc.entities == []


def test_build_prompt_none_si_vacio() -> None:
    assert build_entities_prompt("   ") is None
    assert build_entities_prompt("hola") is not None
