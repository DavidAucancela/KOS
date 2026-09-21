"""Plan y salvaguardas de la copia local → gestionado (doc 14 §8). Sin base de datos."""

from __future__ import annotations

from typing import Any

import pytest

from kos_core import data_migration as dm
from kos_core.config import Settings


def test_el_plan_respeta_el_orden_de_las_fks() -> None:
    tables = [t.table for t in dm.copy_plan()]
    assert tables.index("sources") < tables.index("documents") < tables.index("chunks")


def test_el_plan_deja_fuera_el_ruido_de_pruebas_y_lo_que_maneja_el_release() -> None:
    tables = {t.table for t in dm.copy_plan()}
    assert tables == {
        "sources",
        "documents",
        "chunks",
        "node_embeddings",
        "memory_items",
        "recommendations",
    }
    for excluded in ("alembic_version", "cron_runs", "plans", "conversations", "messages"):
        assert excluded not in tables


def test_solo_se_copia_la_fuente_vault_real_y_sus_documentos() -> None:
    by_table = {t.table: t for t in dm.copy_plan()}
    assert by_table["sources"].where == "name = 'vault-real'"
    assert "vault-real" in (by_table["documents"].where or "")
    assert "vault-real" in (by_table["chunks"].where or "")


def test_la_ruta_del_vault_se_reescribe_y_cloud_safe_se_conserva() -> None:
    sources = dm.copy_plan("/data/vault")[0]
    sql = dm.select_sql(sources, ["source_uuid", "name", "config"])
    assert "jsonb_set(config, '{vault_path}', to_jsonb('/data/vault'::text)) AS \"config\"" in sql
    # `cloud_safe` no se toca: jsonb_set solo cambia `vault_path`.
    assert "cloud_safe" not in sql


@pytest.mark.parametrize("bad", ["", "vault", "/data/vault'; DROP TABLE sources; --", "/a b"])
def test_rechaza_rutas_de_vault_que_no_sean_seguras(bad: str) -> None:
    with pytest.raises(ValueError, match="ruta de vault"):
        dm.copy_plan(bad)


class _FakeCursor:
    """Devuelve las columnas que `information_schema` daría para `chunks`."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[tuple[str]]:
        return [("chunk_id",), ("doc_id",), ("text",), ("position",)]


def test_las_columnas_generadas_se_excluyen_de_la_consulta() -> None:
    cur = _FakeCursor()
    columns = dm.copy_columns(cur, "chunks")  # type: ignore[arg-type]
    [(sql, params)] = cur.executed
    assert "is_generated = 'NEVER'" in sql  # `text_search` (to_tsvector) queda fuera
    assert params == ("chunks",)
    assert columns == ["chunk_id", "doc_id", "text", "position"]


def test_select_y_count_filtran_por_la_fuente() -> None:
    documents = {t.table: t for t in dm.copy_plan()}["documents"]
    assert dm.select_sql(documents, ["doc_id"]).startswith('SELECT "doc_id" FROM "documents" WHERE')
    assert dm.count_sql(dm.TableCopy("node_embeddings")) == 'SELECT count(*) FROM "node_embeddings"'


def test_el_origen_ignora_database_url() -> None:
    """Si el shell tiene DATABASE_URL apuntando a Supabase, `postgres_dsn` lo daría
    como origen: la copia debe usar solo las piezas locales."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://postgres.x:secreto@aws-0.pooler.supabase.com:5432/postgres",
        postgres_host="localhost",
        postgres_port=5434,
        postgres_db="kos",
    )
    info = dm.source_conninfo(settings)
    assert "supabase" not in info
    assert "host=localhost" in info and "port=5434" in info


def test_rechaza_origen_y_destino_iguales() -> None:
    src = "host=localhost port=5434 dbname=kos user=kos password=x"
    with pytest.raises(ValueError, match="la misma base"):
        dm.ensure_distinct_targets(src, "postgresql://kos:y@localhost:5434/kos")


def test_rechaza_un_destino_local_salvo_que_se_permita() -> None:
    src = "host=localhost port=5434 dbname=kos user=kos password=x"
    other_local = "postgresql://kos:x@localhost:5434/otra_base"
    with pytest.raises(ValueError, match="destino es local"):
        dm.ensure_distinct_targets(src, other_local)
    dm.ensure_distinct_targets(src, other_local, allow_local_target=True)


def test_acepta_un_destino_gestionado() -> None:
    src = "host=localhost port=5434 dbname=kos user=kos password=x"
    dm.ensure_distinct_targets(
        src, "postgresql://postgres.ref:x@aws-0-us-west-1.pooler.supabase.com:5432/postgres"
    )


def test_check_source_pide_exactamente_una_fuente_con_documentos() -> None:
    ok = {"sources": 1, "documents": 804, "chunks": 2717}
    assert dm.check_source(ok) == []
    assert any("0 fuentes" in p for p in dm.check_source({**ok, "sources": 0}))
    assert any("2 fuentes" in p for p in dm.check_source({**ok, "sources": 2}))
    assert any("no tiene documentos" in p for p in dm.check_source({**ok, "documents": 0}))
    # Sin claves (origen vacío): ambos problemas, no un KeyError.
    assert len(dm.check_source({})) == 2


def test_todas_las_tablas_del_plan_tienen_clave_para_la_huella() -> None:
    assert all(t.key for t in dm.copy_plan())


def test_la_huella_filtra_el_origen_pero_no_el_destino() -> None:
    chunks = {t.table: t for t in dm.copy_plan()}["chunks"]
    source_sql = dm.fingerprint_sql(chunks, filtered=True)
    destination_sql = dm.fingerprint_sql(chunks, filtered=False)
    assert source_sql is not None and destination_sql is not None
    assert "WHERE" in source_sql and "WHERE" not in destination_sql
    assert 'string_agg("chunk_id"::text' in source_sql
    assert dm.fingerprint_sql(dm.TableCopy("sin_clave"), filtered=True) is None


class _TypesCursor:
    def __init__(self, rows: list[tuple[str, str]]) -> None:
        self.rows = rows
        self.sql = ""

    def execute(self, sql: str, params: Any = None) -> None:
        self.sql = sql

    def fetchall(self) -> list[tuple[str, str]]:
        return self.rows


def test_la_paridad_compara_tipos_exactos_y_no_solo_nombres() -> None:
    plan = [dm.TableCopy("node_embeddings")]
    same_names_other_type = [("node_id", "text"), ("embedding", "vector(768)")]
    original = [("node_id", "text"), ("embedding", "vector(1024)")]
    src, dst = _TypesCursor(original), _TypesCursor(same_names_other_type)
    problems = dm.check_parity(src, dst, plan)  # type: ignore[arg-type]
    assert problems and "vector(768)" in problems[0]
    assert dm.check_parity(_TypesCursor(original), _TypesCursor(original), plan) == []  # type: ignore[arg-type]
    assert "attgenerated = ''" in src.sql and "format_type" in src.sql


def test_la_paridad_avisa_si_una_tabla_no_existe() -> None:
    problems = dm.check_parity(
        _TypesCursor([("a", "text")]),  # type: ignore[arg-type]
        _TypesCursor([]),  # type: ignore[arg-type]
        [dm.TableCopy("memory_items")],
    )
    assert any("no existe" in p for p in problems)
