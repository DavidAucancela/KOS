"""pg_trgm y RLS: lo que el despliegue gestionado necesita y local ya tenía (doc 14 §8).

Dos brechas que la fase C dejó sin ver porque el esquema local nace con
`infra/postgres/init.sql` y el de Supabase solo con estas migraciones:

1. **`pg_trgm`.** `search.py` usa `word_similarity` en la rama de título de la
   búsqueda híbrida. Solo `init.sql` creaba la extensión, así que en Supabase toda
   búsqueda fallaba con `function word_similarity does not exist`.
2. **RLS.** Supabase expone el schema `public` por su Data API: sin RLS, la clave
   `anon` puede leer y modificar cada fila. Se activa **sin políticas**: bloquea a
   `anon`/`authenticated` y no toca a la app, que conecta como `postgres` (o como el
   dueño de las tablas en local), ambos con BYPASSRLS o exentos por ser dueños.

Activa RLS en las tablas que existan en `public` (no en una lista fija): así vale
igual con las 13 de Supabase y con las 11 de una base local que se quedó sin
`memory_proposals` por las dos migraciones `0012`. Una tabla nueva hay que
protegerla en su propia migración; `test_rls_integration.py` avisa si se olvida.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-21

"""

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | None = None
depends_on: str | None = None


def _for_each_public_table(action: str) -> str:
    return f"""
        DO $$
        DECLARE t text;
        BEGIN
            FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
                EXECUTE format('ALTER TABLE public.%I {action} ROW LEVEL SECURITY', t);
            END LOOP;
        END $$;
    """


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(_for_each_public_table("ENABLE"))


def downgrade() -> None:
    # `pg_trgm` se queda: quitarlo rompería la búsqueda local, que ya dependía de él.
    op.execute(_for_each_public_table("DISABLE"))
