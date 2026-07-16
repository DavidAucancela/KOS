import uuid

from kos_core.storage.search import RRF_K, rrf_fuse


def _ids(count: int) -> list[uuid.UUID]:
    return [uuid.UUID(int=index) for index in range(1, count + 1)]


def test_rrf_fusiona_rankings_solapados() -> None:
    id_a, id_b, id_c = _ids(3)
    fused = rrf_fuse([[id_a, id_b], [id_b, id_c]], k=60)

    ids = [item for item, _ in fused]
    assert ids[0] == id_b  # aparece en ambos rankings: gana
    assert set(ids) == {id_a, id_b, id_c}

    score_b = dict(fused)[id_b]
    assert abs(score_b - (1 / 61 + 1 / 62)) < 1e-12


def test_rrf_k_por_defecto() -> None:
    [only] = _ids(1)
    [(_, score)] = rrf_fuse([[only]])
    assert abs(score - 1 / (RRF_K + 1)) < 1e-12


def test_rrf_empates_deterministas() -> None:
    id_a, id_b = _ids(2)
    # Mismo score en ambos órdenes de entrada: el desempate por UUID fija el resultado.
    assert rrf_fuse([[id_a], [id_b]]) == rrf_fuse([[id_b], [id_a]])


def test_rrf_listas_vacias() -> None:
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_rrf_ordena_descendente() -> None:
    ids = _ids(4)
    fused = rrf_fuse([ids, ids])
    scores = [score for _, score in fused]
    assert scores == sorted(scores, reverse=True)
    assert [item for item, _ in fused] == ids
