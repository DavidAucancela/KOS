"""Copia de datos local → gestionado (Railway fase D, doc 14 §8).

Lleva el conocimiento ya calculado en la base local a Supabase sin re-ingerir
(re-ingerir cuesta el backfill completo de LLM cloud). No es un `pg_dump`:

- **Solo datos.** El esquema ya lo creó el `releaseCommand` (`alembic upgrade head`).
- **Sin `--disable-triggers`.** Exige superusuario y el rol `postgres` de Supabase no lo
  es; además la base no tiene triggers de usuario, solo 4 FKs, así que basta el orden.
- **Columnas generadas fuera.** `chunks.text_search` es `GENERATED ALWAYS`: un `COPY`
  que la nombre falla. Se toman las columnas de `information_schema` sin las generadas.
- **Alcance: solo conocimiento** (decisión del 2026-09-21). Fuentes de prueba,
  conversaciones, mensajes y planes locales no se copian (ver `copy_plan`).

Seguridad: el origen se abre en solo lectura (nunca se escribe en local); todo el
`copy` es **una transacción** en el destino, así que un fallo no deja nada a medias;
y se rechaza que origen y destino sean la misma base (p. ej. si el shell tiene
`DATABASE_URL` apuntando a Supabase, `Settings.postgres_dsn` lo daría como origen).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from kos_core.config import Settings

EXPECTED_REVISION = "0017"
SOURCE_NAME = "vault-real"
DEFAULT_VAULT_PATH = "/data/vault"
LOCAL_HOSTS = frozenset({"", "localhost", "127.0.0.1", "::1"})
_VAULT_PATH_RE = re.compile(r"/[A-Za-z0-9_./-]+")

Cursor = psycopg.Cursor[Any]
Connection = psycopg.Connection[Any]


@dataclass(frozen=True)
class TableCopy:
    """Una tabla a copiar. `where` y `overrides` son SQL fijo de este módulo, nunca
    entrada del usuario (el único valor externo, la ruta del vault, se valida)."""

    table: str
    where: str | None = None
    overrides: Mapping[str, str] = field(default_factory=dict)


def copy_plan(vault_path: str = DEFAULT_VAULT_PATH) -> list[TableCopy]:
    """Tablas a copiar, en orden de FKs (`sources → documents → chunks`).

    **No** se copian: `alembic_version` (la maneja el `releaseCommand`), `cron_runs`,
    `pending_vault_writes`, `plans`, `conversations` y `messages` (ruido de pruebas
    locales) ni las fuentes `mini-vault`/`vault-auto` con sus documentos.

    `sources.config.vault_path` se reescribe: en local es una ruta de macOS que en
    Railway no existe; el cron clona el vault en `/data/vault`. `cloud_safe` se
    conserva (ADR-0008)."""
    if not _VAULT_PATH_RE.fullmatch(vault_path):
        raise ValueError(f"ruta de vault no válida: {vault_path!r}")
    vault_sources = f"SELECT source_uuid FROM sources WHERE name = '{SOURCE_NAME}'"
    vault_docs = f"SELECT doc_id FROM documents WHERE source_uuid IN ({vault_sources})"
    return [
        TableCopy(
            "sources",
            where=f"name = '{SOURCE_NAME}'",
            overrides={
                "config": f"jsonb_set(config, '{{vault_path}}', to_jsonb('{vault_path}'::text))"
            },
        ),
        TableCopy("documents", where=f"source_uuid IN ({vault_sources})"),
        TableCopy("chunks", where=f"doc_id IN ({vault_docs})"),
        TableCopy("node_embeddings"),
        TableCopy("memory_items"),
        TableCopy("recommendations"),
    ]


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def select_sql(table_copy: TableCopy, columns: list[str]) -> str:
    projected = ", ".join(
        f"{table_copy.overrides[c]} AS {_ident(c)}" if c in table_copy.overrides else _ident(c)
        for c in columns
    )
    sql = f"SELECT {projected} FROM {_ident(table_copy.table)}"
    return f"{sql} WHERE {table_copy.where}" if table_copy.where else sql


def count_sql(table_copy: TableCopy) -> str:
    sql = f"SELECT count(*) FROM {_ident(table_copy.table)}"
    return f"{sql} WHERE {table_copy.where}" if table_copy.where else sql


def copy_columns(cur: Cursor, table: str) -> list[str]:
    """Columnas copiables de `table`, en orden, sin las generadas."""
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND is_generated = 'NEVER' "
        "ORDER BY ordinal_position",
        (table,),
    )
    return [row[0] for row in cur.fetchall()]


def source_conninfo(settings: Settings) -> str:
    """Conexión al origen **solo con las piezas locales**, ignorando `database_url`."""
    return make_conninfo(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )


def ensure_distinct_targets(
    source: str, destination: str, *, allow_local_target: bool = False
) -> None:
    """Rechaza copiar una base sobre sí misma y, salvo `allow_local_target`, copiar
    hacia una base local (el destino de la fase D es Supabase)."""
    src, dst = conninfo_to_dict(source), conninfo_to_dict(destination)
    key = ("host", "port", "dbname")
    if all(str(src.get(k, "")) == str(dst.get(k, "")) for k in key):
        raise ValueError("origen y destino son la misma base: se aborta")
    if not allow_local_target and str(dst.get("host", "")) in LOCAL_HOSTS:
        raise ValueError(
            "el destino es local: la fase D copia hacia Supabase "
            "(usa --allow-local-target solo para pruebas)"
        )


def connect(conninfo: str, *, read_only: bool) -> Connection:
    conn = psycopg.connect(conninfo)
    # `read_only` usa `BEGIN READ ONLY`: no depende de parámetros de arranque, que los
    # pooler de Supabase pueden rechazar.
    conn.read_only = read_only
    return conn


def check_destination(cur: Cursor, plan: list[TableCopy]) -> list[str]:
    """Problemas que impiden copiar al destino (lista vacía = listo)."""
    problems: list[str] = []
    cur.execute("SELECT version_num FROM alembic_version")
    row = cur.fetchone()
    revision = row[0] if row else None
    if revision != EXPECTED_REVISION:
        problems.append(
            f"alembic_version del destino es {revision!r}, se esperaba {EXPECTED_REVISION!r}"
        )
    cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
    if cur.fetchone() is None:
        problems.append("falta la extensión pg_trgm en el destino (la crea la migración 0017)")
    cur.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity ORDER BY 1"
    )
    without_rls = [r[0] for r in cur.fetchall()]
    if without_rls:
        problems.append(f"tablas del destino sin RLS (migración 0017): {without_rls}")
    for table_copy in plan:
        cur.execute(f"SELECT count(*) FROM {_ident(table_copy.table)}")
        count = cur.fetchone()
        if count and count[0]:
            problems.append(
                f"la tabla {table_copy.table} del destino no está vacía ({count[0]} filas): "
                "esta copia solo carga sobre tablas vacías"
            )
    return problems


def check_parity(source: Cursor, destination: Cursor, plan: list[TableCopy]) -> list[str]:
    """Las columnas copiables deben ser las mismas, en el mismo orden, en ambos lados."""
    problems: list[str] = []
    for table_copy in plan:
        src_cols = copy_columns(source, table_copy.table)
        dst_cols = copy_columns(destination, table_copy.table)
        if src_cols != dst_cols:
            problems.append(f"columnas distintas en {table_copy.table}: {src_cols} vs {dst_cols}")
    return problems


def source_counts(cur: Cursor, plan: list[TableCopy]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_copy in plan:
        cur.execute(count_sql(table_copy))
        row = cur.fetchone()
        counts[table_copy.table] = int(row[0]) if row else 0
    return counts


def run_copy(source: Connection, destination: Connection, plan: list[TableCopy]) -> dict[str, int]:
    """Copia todas las tablas del plan en **una transacción** en el destino: si algo
    falla, se revierte todo. Devuelve las filas que quedaron en cada tabla."""
    inserted: dict[str, int] = {}
    try:
        with destination.cursor() as dcur:
            dcur.execute("SET LOCAL statement_timeout = '15min'")
        for table_copy in plan:
            with source.cursor() as scur:
                columns = copy_columns(scur, table_copy.table)
            column_list = ", ".join(_ident(c) for c in columns)
            copy_out = f"COPY ({select_sql(table_copy, columns)}) TO STDOUT"
            copy_in = f"COPY {_ident(table_copy.table)} ({column_list}) FROM STDIN"
            with source.cursor() as scur, destination.cursor() as dcur:
                with scur.copy(copy_out) as out, dcur.copy(copy_in) as into:
                    for chunk in out:
                        into.write(chunk)
                dcur.execute(f"SELECT count(*) FROM {_ident(table_copy.table)}")
                row = dcur.fetchone()
                inserted[table_copy.table] = int(row[0]) if row else 0
        destination.commit()
    except BaseException:
        # También el origen: un COPY que falla allí deja su transacción abortada.
        destination.rollback()
        source.rollback()
        raise
    return inserted


def verify(
    source: Cursor, destination: Cursor, plan: list[TableCopy], vault_path: str
) -> list[str]:
    """Comprueba el destino tras la copia (lista vacía = todo coincide)."""
    problems: list[str] = []
    expected = source_counts(source, plan)
    for table_copy in plan:
        destination.execute(f"SELECT count(*) FROM {_ident(table_copy.table)}")
        row = destination.fetchone()
        actual = int(row[0]) if row else 0
        if actual != expected[table_copy.table]:
            problems.append(
                f"{table_copy.table}: origen {expected[table_copy.table]} vs destino {actual}"
            )

    active = "SELECT count(*) FROM documents WHERE deleted_at IS NULL"
    tombstones = "SELECT count(*) FROM documents WHERE deleted_at IS NOT NULL"
    vault_docs = (
        f"AND source_uuid IN (SELECT source_uuid FROM sources WHERE name = '{SOURCE_NAME}')"
    )
    for label, sql in (("activos", active), ("tombstones", tombstones)):
        source.execute(f"{sql} {vault_docs}")
        destination.execute(sql)
        src_row, dst_row = source.fetchone(), destination.fetchone()
        if (src_row and src_row[0]) != (dst_row and dst_row[0]):
            problems.append(f"documentos {label}: origen {src_row} vs destino {dst_row}")

    orphan_checks = {
        "documents con source_uuid inexistente": (
            "SELECT count(*) FROM documents d LEFT JOIN sources s USING (source_uuid) "
            "WHERE s.source_uuid IS NULL"
        ),
        "chunks con doc_id inexistente": (
            "SELECT count(*) FROM chunks c LEFT JOIN documents d USING (doc_id) "
            "WHERE d.doc_id IS NULL"
        ),
    }
    for label, sql in orphan_checks.items():
        destination.execute(sql)
        orphan_row = destination.fetchone()
        if orphan_row and orphan_row[0]:
            problems.append(f"{label}: {orphan_row[0]}")

    destination.execute(
        "SELECT config->>'vault_path', config->>'cloud_safe' FROM sources WHERE name = %s",
        (SOURCE_NAME,),
    )
    source_row = destination.fetchone()
    if source_row is None:
        problems.append(f"falta la fuente {SOURCE_NAME} en el destino")
    else:
        if source_row[0] != vault_path:
            problems.append(
                f"vault_path del destino es {source_row[0]!r}, se esperaba {vault_path!r}"
            )
        if source_row[1] != "true":
            problems.append(f"cloud_safe se perdió en la copia (vale {source_row[1]!r})")
    return problems
