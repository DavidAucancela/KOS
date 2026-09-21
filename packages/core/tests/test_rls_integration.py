"""Endurecimiento del esquema para el despliegue gestionado (migración 0017, doc 14 §8).

Requiere `make up` (Postgres arriba) con las migraciones aplicadas. Corre solo con
`-m integration`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from kos_core.config import get_settings
from kos_core.storage.postgres import create_engine

pytestmark = pytest.mark.integration


async def test_toda_tabla_de_public_tiene_rls_activado() -> None:
    """Supabase expone `public` por su Data API: una tabla sin RLS queda abierta a la
    clave `anon`. Si este test falla, la migración que creó la tabla nueva debe hacer
    `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` (ver 0017)."""
    engine = create_engine(get_settings())
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT c.relname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                    "AND NOT c.relrowsecurity ORDER BY 1"
                )
            )
            sin_rls = [row[0] for row in rows]
        assert sin_rls == [], f"tablas de public sin RLS: {sin_rls}"
    finally:
        await engine.dispose()


async def test_pg_trgm_esta_disponible_para_la_busqueda_por_titulo() -> None:
    """`search.py` usa `word_similarity` (pg_trgm). Sin la extensión, toda búsqueda
    falla: en Supabase pasaba porque solo `init.sql` la creaba."""
    engine = create_engine(get_settings())
    try:
        async with engine.connect() as conn:
            score = (
                await conn.execute(text("SELECT word_similarity('docker', 'aprender docker hoy')"))
            ).scalar_one()
        assert score == pytest.approx(1.0)
    finally:
        await engine.dispose()
