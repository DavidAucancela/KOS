"""Descubrimiento de conectores instalados (doc 10 §6)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kos_connectors.base import Connector

_REGISTRY: dict[str, Callable[..., Connector]] = {}


def register(name: str, factory: Callable[..., Connector]) -> None:
    """Registra la fábrica de un conector; el último registro gana."""
    _REGISTRY[name] = factory


def available() -> list[str]:
    """Nombres de los conectores registrados, en orden alfabético."""
    return sorted(_REGISTRY)


def get_connector(name: str, **config: Any) -> Connector:
    """Construye un conector registrado con su configuración."""
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(available()) or "(ninguno)"
        raise KeyError(f"Conector desconocido: {name!r}. Disponibles: {known}") from exc
    return factory(**config)


def _register_builtin() -> None:
    # Import local para evitar ciclos: obsidian importa base, nunca registry.
    from kos_connectors.obsidian.connector import ObsidianConnector

    register("obsidian", ObsidianConnector)


_register_builtin()
