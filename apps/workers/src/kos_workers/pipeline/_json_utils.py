"""Reexporta `kos_core.json_utils` (promovido a core en Sprint 18: `Planner`
en `packages/agents` también lo necesita, no solo s7/s8 acá)."""

from __future__ import annotations

from kos_core.json_utils import strip_code_fence

__all__ = ["strip_code_fence"]
