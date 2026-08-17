"""Herramienta de escritura `obsidian.create_note` (doc 06 §4, Fase 3, deuda
cerrada en Sprint 20): crea una nota real desde una plantilla real de
`_Templates/` en el vault. Requiere aprobación (`kos_mcp.permissions`), mismo
patrón que `memory.store`.

Convive con el comando `/crear-nota` del chat (`apps/api/.../routes/query.py`):
ese camino sigue llamando `kos_core.notes` directo — su propia aprobación ya la
satisface el usuario tecleando el comando explícito (doc 06 §4). Esta tool es
la vía para que un agente (`WritingAgent`, doc 03 §2) cree notas pasando
siempre por el gate real."""

from __future__ import annotations

import uuid
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_core.config import Settings
from kos_core.notes import create_note, get_vault_path
from kos_mcp.permissions import ApprovalRequired, gate


class ObsidianCreateNoteResult(BaseModel):
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
