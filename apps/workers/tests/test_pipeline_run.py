from datetime import UTC, datetime

from kos_core.schemas import RawDocument, make_doc_id
from kos_workers.pipeline import DEFAULT_STAGES, PIPELINE_VERSION, bootstrap, run_pipeline

_NOTA = """---
title: Arquitectura de KOS
author: David
created: 2026-07-01
tags: [kos, arquitectura]
---

Introducción a la arquitectura del sistema y de los conectores.

# Componentes

El núcleo no conoce las fuentes y los conectores entregan documentos.

```python
# esto es código, no un encabezado
print("hola")
```

## Almacenes

Postgres guarda los chunks y Neo4j guarda las relaciones del grafo.
"""


def _raw() -> RawDocument:
    return RawDocument(
        source_id="notas/arquitectura kos.md",
        connector="obsidian",
        content=_NOTA,
        source_metadata={
            "frontmatter": {
                "title": "Arquitectura de KOS",
                "author": "David",
                "created": "2026-07-01",
                "tags": ["kos", "arquitectura"],
            },
            "tags": ["kos", "arquitectura"],
            "links": ["Componentes"],
            "path": "notas/arquitectura kos.md",
            "content_hash": "abc123",
        },
        fetched_at=datetime.now(UTC),
    )


def test_bootstrap_siembra_desde_el_conector() -> None:
    doc = bootstrap(_raw())
    assert doc.doc_id == make_doc_id("obsidian", "notas/arquitectura kos.md")
    assert doc.title == "arquitectura kos"  # provisional: nombre de archivo
    assert doc.body == _NOTA
    assert doc.links == ["Componentes"]
    assert doc.keywords == ["kos", "arquitectura"]


def test_bootstrap_decodifica_bytes() -> None:
    raw = _raw().model_copy(update={"content": "# Título\n\náéí".encode()})
    assert bootstrap(raw).body == "# Título\n\náéí"


def test_run_pipeline_completo() -> None:
    raw = _raw()
    doc = run_pipeline(raw)

    assert doc.title == "Arquitectura de KOS"
    assert doc.author == "David"
    assert doc.created_at == datetime(2026, 7, 1)
    assert doc.language == "es"
    assert doc.body is not None and not doc.body.startswith("---")
    assert doc.keywords == ["kos", "arquitectura"]

    headings = [c.metadata["heading"] for c in doc.chunks]
    assert headings == [None, "Componentes", "Almacenes"]
    for chunk in doc.chunks:
        assert doc.body[chunk.position.start : chunk.position.end] == chunk.text
        assert chunk.doc_id == doc.doc_id


def test_las_etapas_no_mutan_al_documento_previo() -> None:
    doc = bootstrap(_raw())
    snapshot = doc.model_copy(deep=True)
    for stage in DEFAULT_STAGES:
        stage(doc)
    assert doc == snapshot


def test_version_del_pipeline_definida() -> None:
    assert PIPELINE_VERSION == "0.1.0"
