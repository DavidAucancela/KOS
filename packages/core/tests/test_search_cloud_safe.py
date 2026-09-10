"""Propagación de `cloud_safe` fila SQL → SearchHit → EvidenceRef (ADR-0007)."""

import uuid

from kos_core.storage.search import _hit_from_row, evidence_from_hit


def _row(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "chunk_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "text": "algo",
        "metadata": None,
        "title": "T",
        "connector": "obsidian",
        "source_id": "n.md",
        "doc_type": "content",
    }
    base.update(over)
    return base


def test_cloud_safe_true_se_propaga_a_evidence() -> None:
    hit = _hit_from_row(_row(cloud_safe=True), score=0.5, source="vector")
    assert hit.cloud_safe is True
    assert evidence_from_hit(hit).cloud_safe is True


def test_cloud_safe_ausente_o_none_es_false() -> None:
    assert _hit_from_row(_row(), score=0.5, source="lexical").cloud_safe is False
    assert _hit_from_row(_row(cloud_safe=None), score=0.5, source="lexical").cloud_safe is False
    assert evidence_from_hit(_hit_from_row(_row(), score=0.5, source="lexical")).cloud_safe is False
