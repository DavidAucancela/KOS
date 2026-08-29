"""Herramientas de escritura sobre el vault (doc 06 §4, Fase 3). Todas requieren
aprobación (`kos_mcp.permissions`, `WRITE_TOOLS`), mismo patrón que `memory.store`:

- `obsidian.create_note` (deuda cerrada en Sprint 20): crea una nota desde una
  plantilla real de `_Templates/`.
- `obsidian.read_note` / `obsidian.update_note` / `obsidian.create_folder`
  (deuda cerrada 2026-08-26): leer contenido crudo, sobreescribir una nota
  existente, crear una carpeta. `update_note` nunca crea (eso es `create_note`).

`create_note` convive con el comando `/crear-nota` del chat
(`apps/api/.../routes/query.py`): ese camino sigue llamando `kos_core.notes`
directo — su propia aprobación ya la satisface el usuario tecleando el comando
explícito (doc 06 §4). Estas tools son la vía para que un agente (`WritingAgent`,
doc 03 §2) opere sobre el vault pasando siempre por el gate real. No están en el
catálogo del Planner de `/v1/query` (CLAUDE.md regla 7: el LLM no elige
`confirm`)."""

from __future__ import annotations

import uuid
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_core.config import Settings
from kos_core.notes import (
    NoteNotFoundError,
    create_folder,
    create_note,
    get_vault_path,
    read_note,
    update_note,
)
from kos_mcp.permissions import ApprovalRequired, gate


class ObsidianCreateNoteResult(BaseModel):
    approved: bool
    path: str | None
    message: str


class ObsidianReadNoteResult(BaseModel):
    approved: bool
    path: str | None
    content: str | None
    message: str


class ObsidianUpdateNoteResult(BaseModel):
    approved: bool
    path: str | None
    message: str


class ObsidianCreateFolderResult(BaseModel):
    approved: bool
    path: str | None
    message: str


async def _create_note_core(
    engine: Any,
    settings: Settings,
    *,
    template_name: str,
    folder: str,
    title: str,
    source_name: str | None,
    confirm: bool,
    trace_id: str,
) -> ObsidianCreateNoteResult:
    try:
        gate(
            "obsidian.create_note",
            confirm=confirm,
            trace_id=trace_id,
            description=f"crear nota {title!r} desde la plantilla {template_name!r} en {folder!r}",
        )
    except ApprovalRequired as exc:
        return ObsidianCreateNoteResult(approved=False, path=None, message=str(exc))

    vault_path = await get_vault_path(engine, source_name or settings.kos_default_vault_source)
    note_path = create_note(vault_path, template_name=template_name, folder=folder, title=title)
    return ObsidianCreateNoteResult(approved=True, path=str(note_path), message="nota creada")


async def _read_note_core(
    engine: Any,
    settings: Settings,
    *,
    path: str,
    source_name: str | None,
    confirm: bool,
    trace_id: str,
) -> ObsidianReadNoteResult:
    try:
        gate(
            "obsidian.read_note",
            confirm=confirm,
            trace_id=trace_id,
            description=f"leer la nota {path!r}",
        )
    except ApprovalRequired as exc:
        return ObsidianReadNoteResult(approved=False, path=None, content=None, message=str(exc))

    vault_path = await get_vault_path(engine, source_name or settings.kos_default_vault_source)
    try:
        content = read_note(vault_path, path=path)
    except NoteNotFoundError as exc:
        return ObsidianReadNoteResult(approved=True, path=None, content=None, message=str(exc))
    return ObsidianReadNoteResult(
        approved=True, path=path, content=content, message="nota leída"
    )


async def _update_note_core(
    engine: Any,
    settings: Settings,
    *,
    path: str,
    content: str,
    source_name: str | None,
    confirm: bool,
    trace_id: str,
) -> ObsidianUpdateNoteResult:
    try:
        gate(
            "obsidian.update_note",
            confirm=confirm,
            trace_id=trace_id,
            description=f"sobreescribir la nota {path!r}",
        )
    except ApprovalRequired as exc:
        return ObsidianUpdateNoteResult(approved=False, path=None, message=str(exc))

    vault_path = await get_vault_path(engine, source_name or settings.kos_default_vault_source)
    try:
        note_path = update_note(vault_path, path=path, content=content)
    except NoteNotFoundError as exc:
        return ObsidianUpdateNoteResult(approved=True, path=None, message=str(exc))
    return ObsidianUpdateNoteResult(
        approved=True, path=str(note_path), message="nota actualizada"
    )


async def _create_folder_core(
    engine: Any,
    settings: Settings,
    *,
    path: str,
    source_name: str | None,
    confirm: bool,
    trace_id: str,
) -> ObsidianCreateFolderResult:
    try:
        gate(
            "obsidian.create_folder",
            confirm=confirm,
            trace_id=trace_id,
            description=f"crear la carpeta {path!r}",
        )
    except ApprovalRequired as exc:
        return ObsidianCreateFolderResult(approved=False, path=None, message=str(exc))

    vault_path = await get_vault_path(engine, source_name or settings.kos_default_vault_source)
    folder_path = create_folder(vault_path, path=path)
    return ObsidianCreateFolderResult(
        approved=True, path=str(folder_path), message="carpeta creada"
    )


def register(server: MCPServer) -> None:
    @server.tool(name="obsidian.create_note", annotations={"readOnlyHint": False})
    async def obsidian_create_note(
        ctx: Context,
        template_name: str,
        folder: str,
        title: str,
        source_name: str | None = None,
        confirm: bool = False,
        trace_id: str | None = None,
    ) -> ObsidianCreateNoteResult:
        """Crea `folder/{title}.md` en el vault a partir de `_Templates/{template_name}.md`
        (doc 06 §4). Requiere `confirm=true` (doc 06 §4: escrituras piden aprobación por
        defecto). `source_name` por defecto usa `Settings.kos_default_vault_source`."""
        app_ctx = ctx.request_context.lifespan_context
        return await _create_note_core(
            app_ctx.postgres_engine,
            app_ctx.settings,
            template_name=template_name,
            folder=folder,
            title=title,
            source_name=source_name,
            confirm=confirm,
            trace_id=trace_id or str(uuid.uuid4()),
        )

    @server.tool(name="obsidian.read_note", annotations={"readOnlyHint": False})
    async def obsidian_read_note(
        ctx: Context,
        path: str,
        source_name: str | None = None,
        confirm: bool = False,
        trace_id: str | None = None,
    ) -> ObsidianReadNoteResult:
        """Devuelve el contenido crudo de `path` (relativa al vault). Requiere
        `confirm=true` (doc 06 §4). `source_name` por defecto usa
        `Settings.kos_default_vault_source`."""
        app_ctx = ctx.request_context.lifespan_context
        return await _read_note_core(
            app_ctx.postgres_engine,
            app_ctx.settings,
            path=path,
            source_name=source_name,
            confirm=confirm,
            trace_id=trace_id or str(uuid.uuid4()),
        )

    @server.tool(name="obsidian.update_note", annotations={"readOnlyHint": False})
    async def obsidian_update_note(
        ctx: Context,
        path: str,
        content: str,
        source_name: str | None = None,
        confirm: bool = False,
        trace_id: str | None = None,
    ) -> ObsidianUpdateNoteResult:
        """Sobreescribe el contenido de `path` (relativa al vault). La nota debe
        existir — crear es `obsidian.create_note`. Requiere `confirm=true`
        (doc 06 §4)."""
        app_ctx = ctx.request_context.lifespan_context
        return await _update_note_core(
            app_ctx.postgres_engine,
            app_ctx.settings,
            path=path,
            content=content,
            source_name=source_name,
            confirm=confirm,
            trace_id=trace_id or str(uuid.uuid4()),
        )

    @server.tool(name="obsidian.create_folder", annotations={"readOnlyHint": False})
    async def obsidian_create_folder(
        ctx: Context,
        path: str,
        source_name: str | None = None,
        confirm: bool = False,
        trace_id: str | None = None,
    ) -> ObsidianCreateFolderResult:
        """Crea `path` (relativa al vault) y sus padres; idempotente. Requiere
        `confirm=true` (doc 06 §4)."""
        app_ctx = ctx.request_context.lifespan_context
        return await _create_folder_core(
            app_ctx.postgres_engine,
            app_ctx.settings,
            path=path,
            source_name=source_name,
            confirm=confirm,
            trace_id=trace_id or str(uuid.uuid4()),
        )
