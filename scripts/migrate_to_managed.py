"""Copia el conocimiento local a Supabase (Railway fase D, doc 14 §8).

La lógica vive en `kos_core.data_migration` (importable y testeada); este script es la
interfaz de línea de comandos. **Escribe en producción**, así que `copy` exige `--yes`.

Requisitos:
- `make up` (Postgres local con los datos) y la migración `0017` ya desplegada en Supabase
  (`check` lo comprueba).
- `SUPABASE_DB_URL`: URL de conexión del **pooler en modo sesión** (puerto 5432, no el
  transaccional 6543 ni el host directo IPv6), con `?sslmode=require`. Se lee del entorno:
  no se pasa por argumento para que no quede en el historial de la terminal.

Uso (desde la raíz del repo):

    export SUPABASE_DB_URL='postgresql://postgres.<ref>:<clave>@<host-pooler>:5432/postgres?sslmode=require'
    uv run python scripts/migrate_to_managed.py check     # solo lectura: ¿está todo listo?
    uv run python scripts/migrate_to_managed.py copy --yes
    uv run python scripts/migrate_to_managed.py verify    # solo lectura: ¿coincide todo?

Deshacer (solo si `verify` falla tras el commit): `TRUNCATE` de las tablas copiadas en
Supabase — estaban vacías antes, ver `check`. El origen local nunca se escribe.
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlsplit

import psycopg

from kos_core import data_migration as dm
from kos_core.config import get_settings


def _describe(conninfo_url: str) -> str:
    """Host/base sin credenciales, para mostrar a qué se está conectando."""
    parts = urlsplit(conninfo_url)
    return f"{parts.hostname}:{parts.port or 5432}{parts.path}"


def _short(exc: BaseException) -> str:
    """Primera línea del error de conexión: basta para diagnosticar y no arrastra el
    contexto completo del traceback."""
    lines = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {lines[0] if lines else ''}"


def _report(title: str, problems: list[str]) -> bool:
    if problems:
        print(f"✗ {title}")
        for problem in problems:
            print(f"    - {problem}")
        return False
    print(f"✓ {title}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["check", "copy", "verify"])
    parser.add_argument("--vault-path", default=dm.DEFAULT_VAULT_PATH)
    parser.add_argument("--yes", action="store_true", help="confirma la escritura en el destino")
    parser.add_argument("--allow-local-target", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    destination_url = os.environ.get("SUPABASE_DB_URL", "")
    if not destination_url:
        print("Falta SUPABASE_DB_URL (ver el encabezado de este script).", file=sys.stderr)
        return 2

    plan = dm.copy_plan(args.vault_path)
    source_info = dm.source_conninfo(get_settings())
    try:
        dm.ensure_distinct_targets(
            source_info, destination_url, allow_local_target=args.allow_local_target
        )
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2

    writes = args.command == "copy" and args.yes
    print(f"origen : local (solo lectura)\ndestino: {_describe(destination_url)}\n")
    try:
        source = dm.connect(source_info, read_only=True)
    except psycopg.Error as exc:
        print(f"✗ no se pudo conectar al origen (¿`make up`?): {_short(exc)}", file=sys.stderr)
        return 1
    try:
        destination = dm.connect(destination_url, read_only=not writes)
    except psycopg.Error as exc:
        source.close()
        print(
            f"✗ no se pudo conectar al destino: {_short(exc)}\n"
            "  Revisa que SUPABASE_DB_URL sea la del pooler en modo sesión (puerto 5432) y "
            "lleve ?sslmode=require.",
            file=sys.stderr,
        )
        return 1
    try:
        with source.cursor() as scur, destination.cursor() as dcur:
            if args.command == "verify":
                return (
                    0
                    if _report(
                        "el destino coincide con el origen",
                        dm.verify(scur, dcur, plan, args.vault_path),
                    )
                    else 1
                )

            counts = dm.source_counts(scur, plan)
            ready = _report("origen con datos para copiar", dm.check_source(counts))
            ready = _report("destino listo", dm.check_destination(dcur, plan)) and ready
            ready = (
                _report(
                    "esquemas con las mismas columnas y tipos", dm.check_parity(scur, dcur, plan)
                )
                and ready
            )
            print("\nfilas a copiar desde el origen:")
            for table, count in counts.items():
                print(f"    {table:<18}{count:>8}")
            if not ready:
                return 1
            if args.command == "check":
                print("\nTodo listo. Para copiar: copy --yes")
                return 0
        if not args.yes:
            print("\ncopy escribe en el destino: agrega --yes para confirmar.")
            return 2
        print("\ncopiando en una sola transacción...")
        inserted = dm.run_copy(source, destination, plan)
        for table, count in inserted.items():
            print(f"    {table:<18}{count:>8}")
        print("\nCopia confirmada. Ahora corre: verify")
        return 0
    finally:
        source.close()
        destination.close()


if __name__ == "__main__":
    sys.exit(main())
