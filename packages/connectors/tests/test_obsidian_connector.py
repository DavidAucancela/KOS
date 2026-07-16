from pathlib import Path

import pytest

from kos_connectors.base import Connector
from kos_connectors.obsidian import ObsidianConnector


def _refs_por_id(connector: ObsidianConnector) -> dict[str, str]:
    return {ref.source_id: ref.content_hash for ref in connector.discover()}


def test_discover_encuentra_las_notas_e_ignora_ocultos(mini_vault: Path) -> None:
    connector = ObsidianConnector(mini_vault)
    refs = _refs_por_id(connector)
    assert set(refs) == {
        "Docker.md",
        "FastAPI.md",
        "Ideas sueltas.md",
        "proyectos/Proyecto KOS.md",
    }
    assert all("\\" not in source_id for source_id in refs)  # rutas POSIX


def test_discover_hashes_estables(mini_vault: Path) -> None:
    connector = ObsidianConnector(mini_vault)
    assert _refs_por_id(connector) == _refs_por_id(connector)


def test_fetch_nota_con_frontmatter_completo(mini_vault: Path) -> None:
    connector = ObsidianConnector(mini_vault)
    ref = next(r for r in connector.discover() if r.source_id == "FastAPI.md")
    raw = connector.fetch(ref)

    assert raw.connector == "obsidian"
    assert raw.mime_type == "text/markdown"
    assert isinstance(raw.content, str)
    assert raw.content.startswith("---\n")  # contenido íntegro, con frontmatter

    meta = raw.source_metadata
    assert meta["frontmatter"]["title"] == "FastAPI"
    assert meta["frontmatter"]["author"] == "David"
    assert meta["tags"] == ["python", "frameworks", "backend"]
    assert meta["links"] == ["Proyecto KOS", "Docker"]
    assert meta["path"] == "FastAPI.md"
    assert meta["content_hash"] == ref.content_hash


def test_fetch_tags_de_frontmatter_string_y_cuerpo(mini_vault: Path) -> None:
    connector = ObsidianConnector(mini_vault)
    ref = next(r for r in connector.discover() if r.source_id == "Docker.md")
    raw = connector.fetch(ref)
    assert raw.source_metadata["tags"] == ["contenedores", "infraestructura", "devops"]
    assert raw.source_metadata["links"] == ["FastAPI", "Docker"]


def test_fetch_nota_sin_frontmatter(mini_vault: Path) -> None:
    connector = ObsidianConnector(mini_vault)
    ref = next(r for r in connector.discover() if r.source_id == "Ideas sueltas.md")
    raw = connector.fetch(ref)
    assert raw.source_metadata["frontmatter"] == {}
    assert raw.source_metadata["tags"] == ["ideas"]
    assert raw.source_metadata["links"] == ["Proyecto KOS"]


def test_vault_sin_configurar_da_error_claro() -> None:
    connector = ObsidianConnector(vault_path="")
    with pytest.raises(ValueError, match="OBSIDIAN_VAULT_PATH"):
        list(connector.discover())


def test_vault_inexistente(tmp_path: Path) -> None:
    connector = ObsidianConnector(tmp_path / "no-existe")
    with pytest.raises(FileNotFoundError):
        list(connector.discover())


def test_watch_devuelve_iterador_vacio(mini_vault: Path) -> None:
    connector = ObsidianConnector(mini_vault)
    assert list(connector.watch()) == []


def test_cumple_el_protocolo_connector(mini_vault: Path) -> None:
    assert isinstance(ObsidianConnector(mini_vault), Connector)
