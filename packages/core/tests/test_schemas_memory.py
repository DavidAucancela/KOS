"""`effective_salience` (doc 04 §3 paso 4, Sprint 12): decaimiento exponencial
calculado al leer, no mutado en un job aparte."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kos_core.schemas.memory import effective_salience


def test_sin_tiempo_transcurrido_no_decae() -> None:
    now = datetime.now(UTC)
    assert effective_salience(0.8, now, half_life_days=30, now=now) == 0.8


def test_a_una_media_vida_cae_a_la_mitad() -> None:
    now = datetime.now(UTC)
    last_accessed = now - timedelta(days=30)
    assert abs(effective_salience(0.8, last_accessed, half_life_days=30, now=now) - 0.4) < 1e-9


def test_a_dos_medias_vidas_cae_a_un_cuarto() -> None:
    now = datetime.now(UTC)
    last_accessed = now - timedelta(days=60)
    assert abs(effective_salience(0.8, last_accessed, half_life_days=30, now=now) - 0.2) < 1e-9


def test_half_life_no_positiva_no_decae() -> None:
    now = datetime.now(UTC)
    last_accessed = now - timedelta(days=365)
    assert effective_salience(0.8, last_accessed, half_life_days=0, now=now) == 0.8
