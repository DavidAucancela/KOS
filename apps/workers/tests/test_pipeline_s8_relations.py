import uuid

from kos_core.schemas import EntityCandidate, ParsedDocument
from kos_workers.pipeline.s8_relations import build_relations_prompt, make_relations_stage


def _doc(body: str | None, entities: list[EntityCandidate] | None = None) -> ParsedDocument:
    return ParsedDocument(doc_id=uuid.uuid4(), title="t", body=body, entities=entities or [])


def _entity(name: str, type_: str = "Technology") -> EntityCandidate:
    return EntityCandidate(name=name, type=type_)


def test_rellena_relations_con_generate() -> None:
    respuesta = (
        '[{"source": "Proyecto KOS", "relation": "USES", "target": "FastAPI", "confidence": 0.9}]'
    )
    entities = [_entity("Proyecto KOS", "Project"), _entity("FastAPI")]
    stage = make_relations_stage(lambda prompt: respuesta)
    out = stage(_doc("KOS usa FastAPI.", entities))
    assert len(out.relations) == 1
    assert out.relations[0].relation == "USES"


def test_menos_de_dos_entidades_no_llama_a_generate() -> None:
    def generate(prompt: str) -> str:
        raise AssertionError("no debe llamarse con <2 entidades")

    stage = make_relations_stage(generate)
    out = stage(_doc("texto", [_entity("FastAPI")]))
    assert out.relations == []


def test_relacion_con_entidad_desconocida_se_descarta() -> None:
    respuesta = (
        '[{"source": "FastAPI", "relation": "USES", "target": "Fantasma", "confidence": 0.9}]'
    )
    entities = [_entity("FastAPI"), _entity("Docker")]
    stage = make_relations_stage(lambda prompt: respuesta)
    assert stage(_doc("texto", entities)).relations == []


def test_tipo_de_relacion_invalido_se_descarta() -> None:
    respuesta = '[{"source": "FastAPI", "relation": "LIKES", "target": "Docker"}]'
    entities = [_entity("FastAPI"), _entity("Docker")]
    stage = make_relations_stage(lambda prompt: respuesta)
    assert stage(_doc("texto", entities)).relations == []


def test_nombres_canonicalizan_para_matchear() -> None:
    respuesta = '[{"source": "fast-api", "relation": "USES", "target": "docker"}]'
    entities = [_entity("FastAPI"), _entity("Docker")]
    stage = make_relations_stage(lambda prompt: respuesta)
    assert len(stage(_doc("texto", entities)).relations) == 1


def test_no_muta_la_entrada() -> None:
    entities = [_entity("FastAPI"), _entity("Docker")]
    doc = _doc("texto", entities)
    respuesta = '[{"source": "FastAPI", "relation": "USES", "target": "Docker"}]'
    make_relations_stage(lambda prompt: respuesta)(doc)
    assert doc.relations == []


def test_build_prompt_none_con_menos_de_dos_entidades() -> None:
    assert build_relations_prompt("hola", ["FastAPI"]) is None
    assert build_relations_prompt("hola", ["FastAPI", "Docker"]) is not None
