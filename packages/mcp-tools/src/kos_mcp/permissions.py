"""Aprobación de herramientas de escritura (doc 06 §4, doc 10 §8).

Sin Planner ni Plan persistido todavía (Fase 4, sprints posteriores), así que
"aprobación" acá es un gate real y sincrónico, no un flujo async: la escritura
no ocurre sin `confirm=True`, punto. Toda invocación se loguea (JSON
estructurado, `kos_core.observability`) exista o no aprobación — así queda
auditable incluso el intento rechazado.

Sin allowlist ni bypass por variable de entorno: "requiere aprobación por
defecto" (doc 06 §4) significa que el único camino es el gate, no una forma de
saltárselo. Si algún día hace falta un bypass explícito, es una decisión
aparte, con su propio ADR — no un flag que alguien olvida desactivar.
"""

from __future__ import annotations

import logging

from kos_core.observability import bind_trace_id

logger = logging.getLogger("kos_mcp.permissions")

# Registro de herramientas de escritura: `roadmap.*` (Sprints posteriores) se
# suma acá sin tocar los call sites de `gate()`.
WRITE_TOOLS: frozenset[str] = frozenset(
    {"memory.store", "obsidian.create_note", "recommendations.store"}
)


class ApprovalRequired(Exception):
    """`tool_name` es de escritura y se llamó sin `confirm=True`. La tool que
    la lanza la captura y la devuelve como resultado normal de la llamada (no
    un error duro de protocolo MCP) para que quien llamó sepa exactamente qué
    se iba a escribir y pueda reintentar con `confirm=True`."""

    def __init__(self, tool_name: str, description: str) -> None:
        self.tool_name = tool_name
        self.description = description
        super().__init__(f"{tool_name} requiere confirm=true: {description}")


def gate(tool_name: str, *, confirm: bool, trace_id: str, description: str = "") -> None:
    """Verifica permiso de escritura para `tool_name`. No hace nada (ni loguea
    distinto) si `tool_name` no es de escritura — el gate solo importa para
    `WRITE_TOOLS`. Lanza `ApprovalRequired` si es de escritura y falta
    `confirm=True`.
    """
    bind_trace_id(trace_id)
    is_write = tool_name in WRITE_TOOLS
    logger.info(
        "mcp_tool_invocation",
        extra={
            "tool_name": tool_name,
            "is_write": is_write,
            "confirm": confirm,
        },
    )
    if is_write and not confirm:
        raise ApprovalRequired(tool_name, description or f"ejecutar {tool_name}")
