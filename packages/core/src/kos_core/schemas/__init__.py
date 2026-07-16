"""Los contratos de KOS (docs 02 y 06): nada cruza una frontera sin ser un esquema de aquí."""

from kos_core.schemas.agents import (
    AgentRequest,
    AgentResponse,
    Constraints,
    Cost,
    EvidenceRef,
)
from kos_core.schemas.documents import (
    Chunk,
    ChunkPosition,
    ParsedDocument,
    RawDocument,
    make_doc_id,
)
from kos_core.schemas.entities import EntityCandidate, RelationCandidate

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "Chunk",
    "ChunkPosition",
    "Constraints",
    "Cost",
    "EntityCandidate",
    "EvidenceRef",
    "ParsedDocument",
    "RawDocument",
    "RelationCandidate",
    "make_doc_id",
]
