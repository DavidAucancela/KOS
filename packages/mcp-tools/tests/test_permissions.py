"""Tests de `kos_mcp.permissions` (Sprint 16, doc 06 §4): lógica pura, sin infra."""

from __future__ import annotations

import pytest

from kos_mcp.permissions import WRITE_TOOLS, ApprovalRequired, gate


def test_gate_lanza_approval_required_sin_confirm_en_tool_de_escritura() -> None:
    with pytest.raises(ApprovalRequired) as exc_info:
        gate("memory.store", confirm=False, trace_id="trace-1")
    assert exc_info.value.tool_name == "memory.store"


def test_gate_no_lanza_con_confirm_true() -> None:
    gate("memory.store", confirm=True, trace_id="trace-1")  # no debe lanzar


def test_gate_no_lanza_para_herramientas_de_lectura() -> None:
    gate("graph.get_node", confirm=False, trace_id="trace-1")  # no debe lanzar


def test_write_tools_contiene_memory_store() -> None:
    assert "memory.store" in WRITE_TOOLS
    assert "graph.get_node" not in WRITE_TOOLS


def test_write_tools_contiene_obsidian_create_note() -> None:
    """Sprint 20 (deuda cerrada): `obsidian.create_note` migró de la API
    directa a una herramienta MCP real con gate."""
    assert "obsidian.create_note" in WRITE_TOOLS


def test_write_tools_contiene_las_obsidian_restantes() -> None:
    """Deuda cerrada 2026-08-26: `read_note`/`update_note`/`create_folder` se
    implementaron como tools MCP; la tabla del doc 06 §4 las marca escritura."""
    assert {"obsidian.read_note", "obsidian.update_note", "obsidian.create_folder"} <= WRITE_TOOLS


def test_approval_required_incluye_descripcion_legible() -> None:
    with pytest.raises(ApprovalRequired) as exc_info:
        gate(
            "memory.store",
            confirm=False,
            trace_id="trace-1",
            description="guardar memoria sobre 'FastAPI'",
        )
    assert "FastAPI" in exc_info.value.description
    assert "memory.store" in str(exc_info.value)
