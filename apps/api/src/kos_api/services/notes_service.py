"""Crear notas en el vault desde una plantilla real del usuario (doc 06 §4).

Versión mínima directa en la API, no una herramienta MCP (ver nota en
docs/06-apis-y-contratos.md §4): el comando explícito que el usuario teclea en
el chat ya es la aprobación que pide esa regla — no hay ningún agente/LLM
decidiendo escribir de forma autónoma.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage.postgres import sources_table
from kos_core.templater import render_template


class VaultSourceNotFoundError(Exception):
    """La fuente configurada como destino de notas nuevas no está registrada."""


class TemplateNotFoundError(Exception):
    """La plantilla pedida no existe en `_Templates/` del vault."""


class NoteAlreadyExistsError(Exception):
    """Ya existe una nota en la ruta destino; nunca se sobreescribe."""


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
