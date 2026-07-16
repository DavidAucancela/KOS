from pathlib import Path

import pytest

from kos_connectors.obsidian import ObsidianConnector
from kos_connectors.registry import available, get_connector


def test_obsidian_esta_registrado() -> None:
    assert "obsidian" in available()


def test_get_connector_construye_con_config(mini_vault: Path) -> None:
    connector = get_connector("obsidian", vault_path=mini_vault)
    assert isinstance(connector, ObsidianConnector)
    assert len(list(connector.discover())) == 4


def test_conector_desconocido_lanza_keyerror() -> None:
    with pytest.raises(KeyError, match="desconocido"):
        get_connector("gopher")
