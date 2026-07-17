"""Conector de PDFs: extracción de texto + estructura, OCR fuera de alcance (doc 05 §2)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader

from kos_connectors.base import ChangeEvent, SourceRef
from kos_core.schemas import RawDocument

_PAGE_BREAK = "\n\n"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_pages(reader: PdfReader) -> list[str]:
    return [(page.extract_text() or "").strip() for page in reader.pages]


def _extract_title(reader: PdfReader, fallback: str) -> str:
    title = (reader.metadata or {}).get("/Title") if reader.metadata else None
    if title and str(title).strip():
        return str(title).strip()
    outline_title = _first_outline_title(reader)
    if outline_title:
        return outline_title
    return fallback


def _first_outline_title(reader: PdfReader) -> str | None:
    try:
        outline = reader.outline
    except Exception:  # pypdf lanza distintos tipos según el PDF esté mal formado
        return None
    for item in outline:
        if hasattr(item, "title") and str(item.title).strip():
            return str(item.title).strip()
    return None


class PdfConnector:
    """Lee archivos `*.pdf` de un directorio. No parsea más allá del texto crudo."""

    name = "pdf"

    def __init__(self, source_dir: str | Path | None = None) -> None:
        self._source_dir = Path(source_dir).expanduser() if source_dir else None

    @property
    def source_dir(self) -> Path:
        if self._source_dir is None:
            raise ValueError(
                "Directorio de PDFs sin configurar: pasa source_dir al conector "
                "(config del recurso en /v1/sources)"
            )
        return self._source_dir

    def discover(self) -> Iterator[SourceRef]:
        """Enumera los `*.pdf` del directorio, ignorando rutas ocultas."""
        root = self.source_dir
        if not root.is_dir():
            raise FileNotFoundError(f"El directorio de PDFs no existe: {root}")
        for path in sorted(root.rglob("*.pdf")):
            relative = path.relative_to(root)
            if any(part.startswith(".") for part in relative.parts):
                continue
            data = path.read_bytes()
            yield SourceRef(
                source_id=relative.as_posix(),
                uri=str(path),
                content_hash=_sha256(data),
            )

    def fetch(self, ref: SourceRef) -> RawDocument:
        """Extrae texto por página; el hash se recalcula sobre los bytes leídos."""
        path = self.source_dir / ref.source_id
        data = path.read_bytes()
        reader = PdfReader(path)
        pages = _extract_pages(reader)
        title = _extract_title(reader, fallback=Path(ref.source_id).stem)
        content = _PAGE_BREAK.join(pages)
        return RawDocument(
            source_id=ref.source_id,
            connector=self.name,
            content=content,
            mime_type="application/pdf",
            source_metadata={
                "title": title,
                "path": ref.source_id,
                "page_count": len(reader.pages),
                "pages": pages,
                "content_hash": _sha256(data),
            },
            fetched_at=datetime.now(UTC),
            raw_bytes=data,  # blob original a MinIO (doc 05 §2); content es el texto ya extraído
        )

    def watch(self) -> Iterator[ChangeEvent]:
        """Sin watcher todavía: se cubre con sincronización bajo demanda/polling."""
        return iter(())
