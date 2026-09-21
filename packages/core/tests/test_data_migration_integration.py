"""Copia local → gestionado de punta a punta, sobre dos bases desechables (doc 14 §8).

No toca `kos`: crea `kos_mig_src` (sembrada con datos sintéticos) y `kos_mig_dst`
(vacía), las migra desde cero con `alembic upgrade head` y las borra al terminar. Así
se verifica la mecánica del `COPY` (columna generada, `jsonb_set`, vectores, FKs,
tombstones, atomicidad) sin depender de datos reales ni escribir en producción.

Requiere `make up` (Postgres arriba). Corre solo con `-m integration`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from kos_core import data_migration as dm
from kos_core.config import Settings, get_settings

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DB, DST_DB = "kos_mig_src", "kos_mig_dst"


def _conninfo(settings: Settings, dbname: str) -> str:
    return make_conninfo(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=dbname,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )


def _recreate(settings: Settings, dbname: str) -> None:
    with psycopg.connect(_conninfo(settings, "postgres"), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{dbname}"')


def _drop(settings: Settings, dbname: str) -> None:
    with psycopg.connect(_conninfo(settings, "postgres"), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')


def _migrate(dbname: str) -> None:
    env = {**os.environ, "POSTGRES_DB": dbname}
    env.pop("DATABASE_URL", None)
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "packages/core/alembic.ini", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
    )


def _seed(conn: psycopg.Connection[object]) -> tuple[uuid.UUID, uuid.UUID]:
    """Dos fuentes: `vault-real` (la que se migra) y `mini-vault` (basura de pruebas)."""
    real, mini = uuid.uuid4(), uuid.uuid4()
    vector = "array_fill(0.5::real, ARRAY[1024])::vector"
    conn.execute(
        "INSERT INTO sources (source_uuid, name, connector, config, enabled) VALUES "
        "(%s, 'vault-real', 'obsidian', "
        '\'{"cloud_safe": true, "vault_path": "/Users/x/Obsidian Vault"}\', true), '
        "(%s, 'mini-vault', 'obsidian', '{}', true)",
        (real, mini),
    )
    docs = {
        "activo-1": (real, False),
        "activo-2": (real, False),
        "activo-3": (real, False),
        "borrado": (real, True),  # tombstone: se migra, pero sin chunks
        "de-prueba": (mini, False),
    }
    for source_id, (source_uuid, deleted) in docs.items():
        doc_id = uuid.uuid4()
        conn.execute(
            "INSERT INTO documents (doc_id, connector, source_id, fetched_at, source_uuid, "
            "deleted_at) VALUES (%s, 'obsidian', %s, now(), %s, "
            + ("now()" if deleted else "NULL")
            + ")",
            (doc_id, source_id, source_uuid),
        )
        if not deleted:
            for position in range(2):
                conn.execute(
                    "INSERT INTO chunks (chunk_id, doc_id, text, position, embedding) "
                    f"VALUES (%s, %s, %s, %s, {vector})",
                    (uuid.uuid4(), doc_id, f"contenedores docker {source_id} {position}", position),
                )
    for n in range(3):
        conn.execute(
            f"INSERT INTO node_embeddings (node_id, canonical_name, node_type, embedding) "
            f"VALUES (%s, %s, 'Technology', {vector})",
            (f"node-{n}", f"tecnologia {n}"),
        )
    for n in range(2):
        conn.execute(
            "INSERT INTO memory_items (memory_id, type, content) VALUES (%s, 'episodic', %s)",
            (uuid.uuid4(), f"recuerdo {n}"),
        )
    conn.execute(
        "INSERT INTO recommendations (recommendation_id, type, title) VALUES (%s, 'gap', 'Laguna')",
        (uuid.uuid4(),),
    )
    conn.commit()
    return real, mini


@pytest.fixture
def databases() -> Iterator[tuple[str, str]]:
    settings = get_settings()
    _recreate(settings, SRC_DB)
    _recreate(settings, DST_DB)
    try:
        _migrate(SRC_DB)
        _migrate(DST_DB)
        with psycopg.connect(_conninfo(settings, SRC_DB)) as conn:
            _seed(conn)
        yield _conninfo(settings, SRC_DB), _conninfo(settings, DST_DB)
    finally:
        _drop(settings, SRC_DB)
        _drop(settings, DST_DB)


def _counts(conninfo: str, tables: list[str]) -> dict[str, int]:
    with psycopg.connect(conninfo) as conn:
        return {t: conn.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tables}  # type: ignore[index]


def test_la_copia_lleva_solo_el_conocimiento_de_vault_real(databases: tuple[str, str]) -> None:
    src_info, dst_info = databases
    plan = dm.copy_plan("/data/vault")
    tables = [t.table for t in plan]

    dm.ensure_distinct_targets(src_info, dst_info, allow_local_target=True)
    src = dm.connect(src_info, read_only=True)
    dst = dm.connect(dst_info, read_only=False)
    try:
        with src.cursor() as scur, dst.cursor() as dcur:
            # Destino recién migrado desde cero: 0017 (pg_trgm + RLS) aplicado, vacío y
            # con las mismas columnas que el origen.
            assert dm.check_destination(dcur, plan) == []
            assert dm.check_parity(scur, dcur, plan) == []
            expected = dm.source_counts(scur, plan)
        # `mini-vault` y su documento no cuentan: 1 fuente, 4 documentos, 6 chunks.
        assert expected == {
            "sources": 1,
            "documents": 4,
            "chunks": 6,
            "node_embeddings": 3,
            "memory_items": 2,
            "recommendations": 1,
        }

        # Atomicidad: si la última tabla falla, no queda nada de las anteriores.
        with pytest.raises(psycopg.Error):
            dm.run_copy(src, dst, [*plan, dm.TableCopy("no_existe")])
        assert _counts(dst_info, tables) == dict.fromkeys(tables, 0)

        inserted = dm.run_copy(src, dst, plan)
        assert inserted == expected
    finally:
        src.close()
        dst.close()

    src = dm.connect(src_info, read_only=True)
    dst = dm.connect(dst_info, read_only=True)
    try:
        with src.cursor() as scur, dst.cursor() as dcur:
            assert dm.verify(scur, dcur, plan, "/data/vault") == []

            # La ruta de macOS se reescribió y `cloud_safe` sobrevivió (ADR-0008).
            dcur.execute("SELECT name, config FROM sources")
            [(name, config)] = dcur.fetchall()
            assert name == "vault-real"
            assert config == {"cloud_safe": True, "vault_path": "/data/vault"}

            # La columna generada se recalculó en el destino (no se copió).
            dcur.execute("SELECT count(*) FROM chunks WHERE text_search IS NOT NULL")
            assert dcur.fetchone() == (6,)
            # Los vectores llegaron completos.
            dcur.execute("SELECT count(*) FROM chunks WHERE vector_dims(embedding) = 1024")
            assert dcur.fetchone() == (6,)
            # Y la búsqueda por título/trigramas que rompía en Supabase responde.
            dcur.execute("SELECT word_similarity('docker', 'aprender docker')")
            assert dcur.fetchone() == (1.0,)
    finally:
        src.close()
        dst.close()

    # Segunda copia sobre lo ya copiado: `check` la rechaza (solo carga sobre vacío).
    with psycopg.connect(dst_info) as conn, conn.cursor() as cur:
        problems = dm.check_destination(cur, plan)
    assert any("no está vacía" in p for p in problems)
