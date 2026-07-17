import hashlib
from pathlib import Path

import pytest

from kos_connectors.pdf import PdfConnector

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def pdf_connector() -> PdfConnector:
    return PdfConnector(source_dir=FIXTURES)


def test_discover_finds_pdfs(pdf_connector: PdfConnector) -> None:
    refs = list(pdf_connector.discover())
    assert [ref.source_id for ref in refs] == ["sample.pdf"]


def test_discover_content_hash_matches_bytes(pdf_connector: PdfConnector) -> None:
    (ref,) = list(pdf_connector.discover())
    expected = hashlib.sha256((FIXTURES / "sample.pdf").read_bytes()).hexdigest()
    assert ref.content_hash == expected


def test_fetch_extracts_text(pdf_connector: PdfConnector) -> None:
    (ref,) = list(pdf_connector.discover())
    raw = pdf_connector.fetch(ref)
    assert raw.connector == "pdf"
    assert raw.source_id == "sample.pdf"
    assert raw.mime_type == "application/pdf"
    assert "Hola KOS desde un PDF de prueba" in raw.content


def test_fetch_populates_page_metadata(pdf_connector: PdfConnector) -> None:
    (ref,) = list(pdf_connector.discover())
    raw = pdf_connector.fetch(ref)
    assert raw.source_metadata["page_count"] == 1
    assert len(raw.source_metadata["pages"]) == 1
    assert "Hola KOS" in raw.source_metadata["pages"][0]
    assert raw.source_metadata["content_hash"] == ref.content_hash


def test_discover_missing_directory_raises(tmp_path: Path) -> None:
    connector = PdfConnector(source_dir=tmp_path / "no-existe")
    with pytest.raises(FileNotFoundError):
        list(connector.discover())


def test_watch_returns_empty_iterator(pdf_connector: PdfConnector) -> None:
    assert list(pdf_connector.watch()) == []


def test_source_dir_unconfigured_raises() -> None:
    connector = PdfConnector()
    with pytest.raises(ValueError):
        list(connector.discover())
