import uuid

from kos_core.schemas import Chunk, ChunkPosition, ParsedDocument
from kos_workers.pipeline.s4_embeddings import make_embedding_stage


def _doc(n_chunks: int) -> ParsedDocument:
    doc_id = uuid.uuid4()
    chunks = [
        Chunk(
            doc_id=doc_id,
            text=f"texto {i}",
            position=ChunkPosition(order=i, start=0, end=7),
        )
        for i in range(n_chunks)
    ]
    return ParsedDocument(doc_id=doc_id, title="nota", chunks=chunks)


def _fake_embedder(calls: list[list[str]]):  # type: ignore[no-untyped-def]
    def embed_batch(texts: list[str]) -> list[list[float]]:
        calls.append(list(texts))
        return [[float(len(text))] for text in texts]

    return embed_batch


def test_rellena_todos_los_chunks_en_orden() -> None:
    calls: list[list[str]] = []
    stage = make_embedding_stage(_fake_embedder(calls))
    out = stage(_doc(5))
    assert [chunk.embedding for chunk in out.chunks] == [
        [float(len(chunk.text))] for chunk in out.chunks
    ]
    assert len(calls) == 1
    assert len(calls[0]) == 5


def test_respeta_el_batch_size() -> None:
    calls: list[list[str]] = []
    stage = make_embedding_stage(_fake_embedder(calls), batch_size=8)
    out = stage(_doc(20))
    assert [len(batch) for batch in calls] == [8, 8, 4]
    assert all(chunk.embedding is not None for chunk in out.chunks)


def test_documento_sin_chunks_no_llama_al_cliente() -> None:
    calls: list[list[str]] = []
    stage = make_embedding_stage(_fake_embedder(calls))
    doc = ParsedDocument(doc_id=uuid.uuid4(), title="vacía")
    assert stage(doc) is doc
    assert calls == []


def test_no_muta_la_entrada() -> None:
    calls: list[list[str]] = []
    stage = make_embedding_stage(_fake_embedder(calls))
    doc = _doc(3)
    stage(doc)
    assert all(chunk.embedding is None for chunk in doc.chunks)
