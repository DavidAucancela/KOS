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

from kos_core import vault_queue
from kos_core.config import Settings
from kos_core.storage.postgres import documents_table, sources_table
from kos_core.templater import render_template


class VaultSourceNotFoundError(Exception):
    """La fuente configurada como destino de notas nuevas no está registrada."""


class TemplateNotFoundError(Exception):
    """La plantilla pedida no existe en `_Templates/` del vault."""


class NoteAlreadyExistsError(Exception):
    """Ya existe una nota en la ruta destino; nunca se sobreescribe."""


class NoteNotFoundError(Exception):
    """La nota a leer o actualizar no existe en la ruta pedida."""


class VaultPathEscapeError(Exception):
    """La ruta pedida resuelve fuera del vault (path traversal, symlink, ruta
    absoluta). La entrada de `read_note`/`update_note`/`create_folder` puede
    venir de un plan del LLM — mismo criterio de no confianza que el guard de
    SSRF de `web.open` (ver `docs/deuda-tecnica.md`)."""


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


def _resolve_in_vault(vault_path: Path, relative: str) -> Path:
    """Resuelve `relative` dentro de `vault_path`, rechazando cualquier ruta que
    escape del vault (`..`, symlink, ruta absoluta)."""
    vault_resolved = vault_path.resolve()
    candidate = (vault_resolved / relative).resolve()
    if candidate != vault_resolved and not candidate.is_relative_to(vault_resolved):
        raise VaultPathEscapeError(f"Ruta fuera del vault: {relative!r}")
    return candidate


def read_note(vault_path: Path, *, path: str) -> str:
    """Devuelve el contenido crudo de `path` (relativa al vault)."""
    target = _resolve_in_vault(vault_path, path)
    if not target.is_file():
        raise NoteNotFoundError(f"Nota no encontrada: {path}")
    return target.read_text(encoding="utf-8")


def update_note(vault_path: Path, *, path: str, content: str) -> Path:
    """Sobreescribe el contenido de `path` (relativa al vault). La nota debe
    existir — crear es trabajo de `create_note`."""
    target = _resolve_in_vault(vault_path, path)
    if not target.is_file():
        raise NoteNotFoundError(f"Nota no encontrada: {path}")
    target.write_text(content, encoding="utf-8")
    return target


def create_folder(vault_path: Path, *, path: str) -> Path:
    """Crea `path` (relativa al vault) y sus padres. Idempotente."""
    target = _resolve_in_vault(vault_path, path)
    target.mkdir(parents=True, exist_ok=True)
    return target


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


# --- Escrituras diferidas (doc 14 §5) --------------------------------------
#
# En el despliegue gestionado la API no tiene el vault en disco: el volumen está
# en el servicio cron. Estas tres funciones son el único punto donde el sistema
# decide entre escribir ya o encolar, para que los tres call sites (el comando
# del chat, `POST /v1/notes` y las herramientas MCP del WritingAgent) se
# comporten igual sin repetir la decisión.


async def create_note_or_enqueue(
    engine: AsyncEngine,
    settings: Settings,
    *,
    source_name: str,
    template_name: str,
    folder: str,
    title: str,
) -> tuple[str, bool]:
    """Crea la nota, o la encola si este proceso no tiene el vault.

    Devuelve `(ruta, diferida)`. Con `diferida=True` la ruta es la *prevista*:
    aquí no se puede ni leer la plantilla, así que nada se ha renderizado
    todavía.
    """
    if settings.kos_defer_vault_writes:
        await vault_queue.enqueue(
            engine,
            op="create_note",
            source_name=source_name,
            payload={"template_name": template_name, "folder": folder, "title": title},
        )
        return f"{folder}/{title}.md", True
    vault_path = await get_vault_path(engine, source_name)
    return str(
        create_note(vault_path, template_name=template_name, folder=folder, title=title)
    ), False


async def update_note_or_enqueue(
    engine: AsyncEngine, settings: Settings, *, source_name: str, path: str, content: str
) -> tuple[str, bool]:
    if settings.kos_defer_vault_writes:
        await vault_queue.enqueue(
            engine,
            op="update_note",
            source_name=source_name,
            payload={"path": path, "content": content},
        )
        return path, True
    vault_path = await get_vault_path(engine, source_name)
    return str(update_note(vault_path, path=path, content=content)), False


async def create_folder_or_enqueue(
    engine: AsyncEngine, settings: Settings, *, source_name: str, path: str
) -> tuple[str, bool]:
    if settings.kos_defer_vault_writes:
        await vault_queue.enqueue(
            engine, op="create_folder", source_name=source_name, payload={"path": path}
        )
        return path, True
    vault_path = await get_vault_path(engine, source_name)
    return str(create_folder(vault_path, path=path)), False
