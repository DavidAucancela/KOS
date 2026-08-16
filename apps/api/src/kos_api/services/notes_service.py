"""Re-export delgado de `kos_core.notes` (doc 06 §4).

La lógica real vive en `packages/core` desde Sprint 20 (deuda cerrada): la
herramienta MCP `obsidian.create_note` (`packages/mcp-tools`) la necesita
también, y `kos_mcp` no puede depender de `apps/api` (doc 09 §2). Este módulo
se mantiene para no romper los call sites existentes (`routes/query.py`,
`template_intent_service.py`) que ya importan `notes_service.*`.
"""

from __future__ import annotations

from kos_core.notes import (
    NoteAlreadyExistsError,
    TemplateInfo,
    TemplateNotFoundError,
    VaultSourceNotFoundError,
    create_note,
    get_vault_path,
    list_templates,
)

__all__ = [
    "NoteAlreadyExistsError",
    "TemplateInfo",
    "TemplateNotFoundError",
    "VaultSourceNotFoundError",
    "create_note",
    "get_vault_path",
    "list_templates",
]
