import subprocess
from pathlib import Path

import pytest

from kos_connectors.base import Connector
from kos_connectors.git import GitConnector


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _run(repo_path, "init")
    _run(repo_path, "config", "user.email", "kos@example.com")
    _run(repo_path, "config", "user.name", "KOS Test")

    (repo_path / "README.md").write_text("# Proyecto\n\nDescripción inicial.\n", encoding="utf-8")
    _run(repo_path, "add", "README.md")
    _run(repo_path, "commit", "-m", "Añade README inicial")

    docs_dir = repo_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guia.md").write_text("# Guía\n\nContenido.\n", encoding="utf-8")
    _run(repo_path, "add", "docs/guia.md")
    _run(repo_path, "commit", "-m", "Añade guía de uso")

    (repo_path / "main.py").write_text("print('hola')\n", encoding="utf-8")
    _run(repo_path, "add", "main.py")
    _run(repo_path, "commit", "-m", "Añade código fuente")

    node_modules = repo_path / "node_modules" / "paquete"
    node_modules.mkdir(parents=True)
    (node_modules / "vendored.md").write_text("vendored\n", encoding="utf-8")

    return repo_path


def _refs_por_id(connector: GitConnector) -> dict[str, str]:
    return {ref.source_id: ref.content_hash for ref in connector.discover()}


def test_es_un_connector(repo: Path) -> None:
    connector = GitConnector(repo)
    assert isinstance(connector, Connector)
    assert connector.name == "git"


def test_discover_solo_markdown_y_excluye_vendored(repo: Path) -> None:
    connector = GitConnector(repo)
    refs = _refs_por_id(connector)
    assert set(refs) == {"README.md", "docs/guia.md"}


def test_discover_hashes_estables(repo: Path) -> None:
    connector = GitConnector(repo)
    assert _refs_por_id(connector) == _refs_por_id(connector)


def test_fetch_incluye_metadata_del_ultimo_commit(repo: Path) -> None:
    connector = GitConnector(repo)
    ref = next(r for r in connector.discover() if r.source_id == "docs/guia.md")
    raw = connector.fetch(ref)

    assert raw.connector == "git"
    assert raw.source_id == "docs/guia.md"
    assert raw.mime_type == "text/markdown"
    assert "Guía" in raw.content

    last_commit = raw.source_metadata["last_commit"]
    assert last_commit["message"] == "Añade guía de uso"
    assert last_commit["author"] == "KOS Test"
    assert last_commit["commit_hash"]
    assert last_commit["authored_at"]


def test_fetch_readme_usa_su_propio_commit(repo: Path) -> None:
    connector = GitConnector(repo)
    ref = next(r for r in connector.discover() if r.source_id == "README.md")
    raw = connector.fetch(ref)
    assert raw.source_metadata["last_commit"]["message"] == "Añade README inicial"


def test_watch_devuelve_iterador_vacio(repo: Path) -> None:
    connector = GitConnector(repo)
    assert list(connector.watch()) == []


def test_discover_repo_inexistente_lanza_error(tmp_path: Path) -> None:
    connector = GitConnector(tmp_path / "no-existe")
    with pytest.raises(FileNotFoundError):
        list(connector.discover())
