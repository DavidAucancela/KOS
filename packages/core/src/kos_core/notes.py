"""Crear notas en el vault desde una plantilla real del usuario (doc 06 §4).

Promovido desde `apps/api/.../notes_service.py` (Sprint 7-8) porque ahora
cruza el límite `kos_mcp` ↔ `apps/api`: la herramienta MCP `obsidian.create_note`
(`packages/mcp-tools`, deuda cerrada tras Sprint 20) necesita la misma lógica
que el comando `/crear-nota` del chat, y `kos_mcp` no puede depender de
`apps/api` (doc 09 §2, import-linter) — mismo criterio que cualquier tipo o
lógica que cruza una frontera de paquete (CLAUDE.md, regla 2).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage.postgres import documents_table, sources_table
from kos_core.templater import render_template


class VaultSourceNotFoundError(Exception):
    """La fuente configurada como destino de notas nuevas no está registrada."""


class TemplateNotFoundError(Exception):
    """La plantilla pedida no existe en `_Templates/` del vault."""


class NoteAlreadyExistsError(Exception):
    """Ya existe una nota en la ruta destino; nunca se sobreescribe."""


class TemplateInfo(BaseModel):
    """Una plantilla real existente en `_Templates/` (Sprint 8)."""

    template_name: str
    """Nombre a pasar como `template_name` a `create_note()` (stem del archivo)."""
    title: str | None
    source_id: str


async def get_vault_path(engine: AsyncEngine, source_name: str) -> Path:
    async with engine.connect() as conn:
        result = await conn.execute(
            select(sources_table.c.config).where(sources_table.c.name == source_name)
        )
        row = result.mappings().first()
    if row is None:
        raise VaultSourceNotFoundError(f"Fuente no registrada: {source_name!r}")
    config: dict[str, Any] = row["config"] or {}
    vault_path = config.get("vault_path")
    if not vault_path:
        raise VaultSourceNotFoundError(f"La fuente {source_name!r} no tiene vault_path configurado")
    return Path(vault_path)


async def list_templates(engine: AsyncEngine) -> list[TemplateInfo]:
    """Plantillas reales indexadas (`doc_type='template'`, ver doc 02 §2), no borradas.

    Query directa (no similaridad): usada para la pregunta de aclaración cuando
    la intención de plantilla es ambigua (Sprint 8).
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            select(documents_table.c.title, documents_table.c.source_id).where(
                documents_table.c.doc_type == "template",
                documents_table.c.deleted_at.is_(None),
            )
        )
        rows = result.mappings().all()
    return [
        TemplateInfo(
            template_name=PurePosixPath(row["source_id"]).stem,
            title=row["title"],
            source_id=row["source_id"],
        )
        for row in rows
    ]


def create_note(vault_path: Path, *, template_name: str, folder: str, title: str) -> Path:
    """Renderiza `_Templates/{template_name}.md` y la escribe en `folder/{title}.md`.

    Nunca sobreescribe una nota existente.
    """
    template_path = vault_path / "_Templates" / f"{template_name}.md"
    if not template_path.is_file():
        raise TemplateNotFoundError(f"Plantilla no encontrada: {template_path}")

    target_path = vault_path / folder / f"{title}.md"
    if target_path.exists():
        raise NoteAlreadyExistsError(f"Ya existe una nota en: {target_path}")

    rendered = render_template(
        template_path.read_text(encoding="utf-8"),
        title=title,
        date=date.today().isoformat(),
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(rendered, encoding="utf-8")
    return target_path
