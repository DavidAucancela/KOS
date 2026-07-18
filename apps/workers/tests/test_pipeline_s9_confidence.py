import uuid

from kos_core.schemas import EntityCandidate, ParsedDocument
from kos_workers.pipeline.s9_confidence import apply_confidence_rules


def _doc(entities: list[EntityCandidate]) -> ParsedDocument:
    return ParsedDocument(doc_id=uuid.uuid4(), title="t", entities=entities)


def test_sube_confianza_por_cada_alias() -> None:
    entity = EntityCandidate(name="FastAPI", type="Technology", confidence=0.5, aliases=["fa"])
    out = apply_confidence_rules(_doc([entity]))
    assert out.entities[0].confidence == 0.55


def test_no_supera_uno() -> None:
    entity = EntityCandidate(
        name="FastAPI", type="Technology", confidence=0.99, aliases=["a", "b", "c"]
    )
    out = apply_confidence_rules(_doc([entity]))
    assert out.entities[0].confidence == 1.0


def test_sin_alias_no_cambia() -> None:
    entity = EntityCandidate(name="FastAPI", type="Technology", confidence=0.5)
    out = apply_confidence_rules(_doc([entity]))
    assert out.entities[0].confidence == 0.5


def test_no_muta_la_entrada() -> None:
    entity = EntityCandidate(name="FastAPI", type="Technology", confidence=0.5, aliases=["fa"])
    doc = _doc([entity])
    apply_confidence_rules(doc)
    assert doc.entities[0].confidence == 0.5
