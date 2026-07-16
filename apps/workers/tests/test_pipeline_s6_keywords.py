import uuid

from kos_core.schemas import ParsedDocument
from kos_workers.pipeline.s6_keywords import extract_keywords


def _doc(*, body: str, keywords: list[str] | None = None) -> ParsedDocument:
    return ParsedDocument(doc_id=uuid.uuid4(), title="t", body=body, keywords=keywords or [])


def test_existentes_van_primero_y_se_conservan() -> None:
    doc = _doc(body="docker docker contenedores", keywords=["infra"])
    out = extract_keywords(doc)
    assert out.keywords[0] == "infra"
    assert "docker" in out.keywords


def test_deduplica_sin_distinguir_mayusculas() -> None:
    doc = _doc(body="Docker docker DOCKER", keywords=["Docker"])
    out = extract_keywords(doc)
    lowered = [kw.lower() for kw in out.keywords]
    assert lowered.count("docker") == 1
    assert out.keywords[0] == "Docker"  # conserva el casing del existente


def test_quita_stopwords() -> None:
    doc = _doc(body="the and para con docker docker")
    out = extract_keywords(doc)
    assert "docker" in out.keywords
    assert "the" not in out.keywords
    assert "para" not in out.keywords


def test_ordena_por_frecuencia_y_recorta_a_max() -> None:
    body = "alfa alfa alfa beta beta gamma delta epsilon zeta eta theta iota kappa"
    doc = _doc(body=body)
    out = extract_keywords(doc, max_keywords=3)
    assert out.keywords == ["alfa", "beta", "gamma"]


def test_no_muta_la_entrada() -> None:
    doc = _doc(body="docker contenedores", keywords=["infra"])
    original = list(doc.keywords)
    extract_keywords(doc)
    assert doc.keywords == original
