# packages/core

**El corazón compartido de KOS.** No depende de ningún otro paquete interno.

Contiene:

- Esquemas Pydantic: `RawDocument`, `ParsedDocument`, `Chunk`, `EntityCandidate`, `RelationCandidate`, `MemoryItem` ([doc 02](../../docs/02-modelo-de-dominio-y-ontologia.md))
- Contratos de agentes: `AgentRequest`, `AgentResponse` ([doc 03](../../docs/03-arquitectura-de-agentes.md))
- Esquemas de eventos del bus ([doc 06](../../docs/06-apis-y-contratos.md))
- Ontología del grafo (tipos de nodo/relación como código)
- Interfaz abstracta de LLM y embeddings (Ollama por defecto, [ADR-0006](../../docs/adr/0006-local-first-con-ollama.md))
- Configuración tipada (`pydantic-settings`)

Regla: **nada cruza una frontera de dominio sin ser un esquema de este paquete.**
