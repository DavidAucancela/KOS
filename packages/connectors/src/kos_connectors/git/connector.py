"""Conector de repos Git locales: discover/fetch sobre README y docs (doc 05 §2).

Fase 1 solo indexa documentación (README, `*.md`); el código fuente como
documento queda para Fase 2+. No clona el repo: opera sobre un working tree
ya presente en disco.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kos_connectors.base import ChangeEvent, SourceRef
from kos_core.schemas import RawDocument

_EXCLUDED_DIR_NAMES = {".git", "node_modules", "vendor", "dist", "build", ".venv"}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_git(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


class GitConnector:
    """Lee README y markdown de documentación de un repo git local ya clonado."""

    name = "git"

    def __init__(self, repo_path: str | Path) -> None:
        self._repo_path = Path(repo_path).expanduser()

    @property
    def repo_path(self) -> Path:
        return self._repo_path

    def discover(self) -> Iterator[SourceRef]:
        """Enumera README(s) y `*.md` del repo, fuera de directorios vendored/`.git`."""
        repo = self._repo_path
        if not repo.is_dir():
            raise FileNotFoundError(f"El repo no existe o no es un directorio: {repo}")
        for path in sorted(repo.rglob("*.md")):
            relative = path.relative_to(repo)
            if any(part in _EXCLUDED_DIR_NAMES for part in relative.parts):
                continue
            text = path.read_text(encoding="utf-8")
            yield SourceRef(
                source_id=relative.as_posix(),
                uri=str(path),
                content_hash=_sha256(text),
            )

    def fetch(self, ref: SourceRef) -> RawDocument:
        """Contenido del archivo + metadata del último commit que lo tocó."""
        path = self._repo_path / ref.source_id
        text = path.read_text(encoding="utf-8")
        return RawDocument(
            source_id=ref.source_id,
            connector=self.name,
            content=text,
            mime_type="text/markdown",
            source_metadata={
                "path": ref.source_id,
                "content_hash": _sha256(text),
                "last_commit": self._last_commit(ref.source_id),
            },
            fetched_at=datetime.now(UTC),
        )

    def watch(self) -> Iterator[ChangeEvent]:
        """Sin polling/webhooks en Fase 1: se cubre con sincronización bajo demanda."""
        return iter(())

    def _last_commit(self, source_id: str) -> dict[str, Any] | None:
        """Autor, fecha ISO, hash y mensaje del commit más reciente sobre `source_id`."""
        separator = "\x1f"
        output = _run_git(
            self._repo_path,
            "log",
            "-1",
            f"--format=%H{separator}%an{separator}%aI{separator}%s",
            "--",
            source_id,
        ).strip()
        if not output:
            return None
        commit_hash, author, authored_at, message = output.split(separator)
        return {
            "commit_hash": commit_hash,
            "author": author,
            "authored_at": authored_at,
            "message": message,
        }
