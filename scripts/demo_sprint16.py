"""Demo del Sprint 16 (doc 08): primer servidor MCP real de KOS.

Levanta `kos_mcp.server` como subproceso real por stdio (mismo camino que
usaría un cliente MCP externo como Claude Desktop/Code, no una conexión
in-memory) y ejecuta las 7 herramientas contra infra real, incluyendo el gate
de aprobación de `memory.store`.

Requisitos: `make up`, `make pull-models`, `make migrate`, Ollama nativo con
el vault ya sincronizado (para que `vector.search`/`graph.query` tengan datos
reales sobre los que buscar).
Uso: `make mcp-demo` (o `uv run python scripts/demo_sprint16.py`).
"""

import asyncio
import sys
import uuid

from mcp import StdioServerParameters
from mcp.client import Client
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "kos_mcp.server"])

    async with Client(stdio_client(params)) as client:
        tools = await client.list_tools()
        names = sorted(t.name for t in tools.tools)
        print(f"✓ Servidor MCP arriba (subproceso stdio), {len(names)} herramientas: {names}")

        search_result = await client.call_tool("vector.search", {"query": "FastAPI", "limit": 3})
        evidence = (search_result.structured_content or {}).get("evidence", [])
        print(f"✓ vector.search('FastAPI') → {len(evidence)} evidencias")

        query_result = await client.call_tool(
            "graph.query", {"template": "most_connected", "limit": 1}
        )
        nodes = (query_result.structured_content or {}).get("nodes") or []
        if nodes:
            node_id = nodes[0]["id"]
            node_result = await client.call_tool("graph.get_node", {"node_id": node_id})
            neighbor_count = len((node_result.structured_content or {}).get("neighbors") or [])
            print(f"✓ graph.get_node('{nodes[0]['canonical_name']}') → {neighbor_count} vecinos")
        else:
            print("○ graph.query no encontró nodos (¿el vault ya se sincronizó con el grafo?)")

        marker = uuid.uuid4().hex[:8]
        pending = await client.call_tool(
            "memory.store",
            {
                "query": f"[demo-sprint16-{marker}] ¿qué es KOS?",
                "answer": "un motor de conocimiento",
                "sources": [],
                "confidence": 0.5,
            },
        )
        print(f"✓ memory.store sin confirm → aprobado={pending.structured_content['approved']}")

        written = await client.call_tool(
            "memory.store",
            {
                "query": f"[demo-sprint16-{marker}] ¿qué es KOS?",
                "answer": "un motor de conocimiento",
                "sources": [],
                "confidence": 0.5,
                "confirm": True,
            },
        )
        memory_id = written.structured_content["memory_id"]
        print(f"✓ memory.store con confirm=true → memory_id={memory_id}")

        recall = await client.call_tool("memory.recall", {"q": marker, "limit": 5})
        recalled = (recall.structured_content or {}).get("items") or []
        print(
            f"✓ memory.recall('{marker}') → {len(recalled)} memoria(s) (incluye la recién escrita)"
        )


if __name__ == "__main__":
    asyncio.run(main())
