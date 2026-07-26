"""Conector de vaults de Obsidian: discover/fetch sobre el filesystem (doc 05 §2)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from kos_connectors.base import ChangeEvent, SourceRef
from kos_connectors.obsidian.frontmatter import split_frontmatter
from kos_connectors.obsidian.wikilinks import extract_tags, extract_wikilinks
from kos_core.config import get_settings
from kos_core.schemas import RawDocument


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _frontmatter_tags(frontmatter: dict[str, object]) -> list[str]:
    raw = frontmatter.get("tags")
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(tag) for tag in raw]
    return [str(raw)]


def _doc_type(source_id: str, frontmatter: dict[str, object], tags: list[str]) -> str:
    """Devuelve content o template: carpeta `_Templates/` (misma convención que
    `notes_service.create_note`) o frontmatter/tag `plantilla` como señal adicional."""
    if source_id.startswith("_Templates/"):
        return "template"
    if str(frontmatter.get("tipo", "")).strip().lower() == "plantilla":
        return "template"
    if any(tag.strip().lower() == "plantilla" for tag in tags):
        return "template"
    return "content"


class ObsidianConnector:
    """Lee notas markdown de un vault. No parsea ni toca bases de datos."""

    name = "obsidian"

    def __init__(self, vault_path: str | Path | None = None) -> None:
        raw_path = vault_path if vault_path is not None else get_settings().obsidian_vault_path
        self._vault_path = Path(raw_path).expanduser() if str(raw_path) else None

    @property
    def vault_path(self) -> Path:
        if self._vault_path is None:
            raise ValueError(
                "Vault de Obsidian sin configurar: pasa vault_path al conector "
                "o define OBSIDIAN_VAULT_PATH en el entorno (.env)"
            )
        return self._vault_path

    def discover(self) -> Iterator[SourceRef]:
        """Enumera las notas `*.md` del vault, ignorando directorios ocultos."""
        vault = self.vault_path
        if not vault.is_dir():
            raise FileNotFoundError(f"El vault no existe o no es un directorio: {vault}")
        for path in sorted(vault.rglob("*.md")):
            relative = path.relative_to(vault)
            if any(part.startswith(".") for part in relative.parts):
                continue  # .obsidian, .trash y similares
            text = path.read_text(encoding="utf-8")
            yield SourceRef(
                source_id=relative.as_posix(),
                uri=str(path),
                content_hash=_sha256(text),
            )

    def fetch(self, ref: SourceRef) -> RawDocument:
        """Contenido íntegro de la nota + metadata propia del conector.

        El hash se recalcula sobre lo realmente leído (el archivo pudo cambiar
        entre discover y fetch).
        """
        path = self.vault_path / ref.source_id
        text = path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(text)
        tags = list(dict.fromkeys([*_frontmatter_tags(frontmatter), *extract_tags(body)]))
        return RawDocument(
            source_id=ref.source_id,
            connector=self.name,
            content=text,
            mime_type="text/markdown",
            source_metadata={
                "frontmatter": frontmatter,
                "tags": tags,
                "links": extract_wikilinks(body),
                "path": ref.source_id,
                "content_hash": _sha256(text),
                "doc_type": _doc_type(ref.source_id, frontmatter, tags),
            },
            fetched_at=datetime.now(UTC),
        )

    def watch(self) -> Iterator[ChangeEvent]:
        """Sin watcher todavía: se cubre con sincronización bajo demanda/polling."""
        return iter(())
