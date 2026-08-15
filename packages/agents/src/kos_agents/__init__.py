"""Agentes de KOS (doc 03, doc 10 §7): un Agent es una función async sobre
`AgentRequest`/`AgentResponse` (doc 06 §3). Depende solo de `kos_core` (doc 09
§2) — habla con herramientas vía `ToolCaller` (duck typing, ver `base.py`),
nunca importa `packages/mcp-tools` ni storage/DB directo (ADR-0005)."""
