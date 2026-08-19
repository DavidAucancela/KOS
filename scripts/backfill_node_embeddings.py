"""Backfill de `node_embeddings` (doc 12 §3/§6): puebla la tabla nueva con
embeddings de los nodos que ya existen en Neo4j, para que la resolución de
entidades indexada (`graph_sync.py::_resolve_entity`) tenga cobertura completa
desde el primer documento que se reingiera después de correr esto.

Se corre una sola vez, a mano, tras aplicar la migración `0010_node_embeddings`
— no es parte del pipeline automático (doc 12 §3 lo deja explícito: la
migración solo crea la tabla, este script la puebla por separado).

Recorre todos los tipos de nodo de la ontología cerrada (`kos_core.ontology`),
trae los nodos existentes de Neo4j por tipo (`fetch_nodes_by_type`), embedea
`canonical_name` en lotes vía Ollama (mismo modelo bge-m3 que ya usan los
chunks) y persiste con `upsert_node_embedding` — idempotente, correr de nuevo
solo reescribe lo mismo.

Requisitos: `make up` (Postgres + Neo4j), Ollama con `bge-m3` descargado.

Uso: `uv run python scripts/backfill_node_embeddings.py`
"""

from __future__ import annotations

import asyncio

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.ontology import NODE_TYPES
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage.postgres import create_engine, upsert_node_embedding

BATCH_SIZE = 50


async def _backfill() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)

    total = 0
    try:
        for node_type in NODE_TYPES:
            nodes = await neo4j_storage.fetch_nodes_by_type(driver, node_type)
            if not nodes:
                continue
            for start in range(0, len(nodes), BATCH_SIZE):
                batch = nodes[start : start + BATCH_SIZE]
                names = [node.get("name") or node["canonical_name"] for node in batch]
                vectors = await embedder.embed(names)
                for node, vector in zip(batch, vectors, strict=True):
                    await upsert_node_embedding(
                        engine,
                        node_id=str(node["id"]),
                        canonical_name=node["canonical_name"],
                        node_type=node_type,
                        embedding=vector,
                    )
                total += len(batch)
                print(f"  {node_type}: {min(start + BATCH_SIZE, len(nodes))}/{len(nodes)}")
    finally:
        await embedder.aclose()
        await driver.close()
        await engine.dispose()

    print(f"✓ {total} nodos embebidos en node_embeddings")


def main() -> None:
    asyncio.run(_backfill())


if __name__ == "__main__":
    main()
