"""WritingAgent (doc 03 §2): redacta la respuesta final con citas a partir de la
evidencia ya fusionada por pasos previos del plan (retrieval/graph/memory).

`__call__` (la síntesis con el LLM) no llama ninguna herramienta MCP — es el
paso final del plan, no una capacidad de storage (doc 03 §2 lo lista como
agente propio, no como wrapper de una tool). Envuelve la lógica que hasta
Sprint 17 vivía inline en
`apps/api/.../query_service.py::answer_query` (`_build_context`, `_SYSTEM_PROMPT`,
`llm.generate(...)`), Sprint 18 la promueve a agente real para que el Planner
pueda tratarla como cualquier otro paso del plan (mismo contrato
`AgentRequest`/`AgentResponse`).

`llm.generate(..., timeout=request.constraints.timeout_s)` (auditoría de
cierre v0.5, 2026-08-16): antes la llamada real a Ollama usaba el timeout fijo
del cliente (120s) sin importar el presupuesto declarado del plan — la
síntesis, siendo el paso más lento típico, era el caso más visible de esa
desconexión.

Capacidad de escritura sobre el vault (doc 03 §2: "crea/modifica notas", deuda
cerrada 2026-08-26): los métodos `read_note`/`update_note`/`create_folder`
envuelven las tools MCP `obsidian.*` forzando `confirm=True` por código — mismo
patrón que `LearningAgent`/`RecommenderAgent` (el sistema completa una acción ya
aprobada fuera de banda, no un LLM eligiendo escribir). La frontera de seguridad
(CLAUDE.md regla 7: el Planner-LLM de `/v1/query` nunca elige `confirm=true`) es
que estos métodos NO se alcanzan desde `__call__` ni desde el `_CATALOG` del
Planner — quedan listos para un flujo explícito futuro, igual que `MemoryAgent`
se construyó standalone en Sprint 17 antes de conectarse."""

from __future__ import annotations

import time
from typing import Any

from kos_agents.base import ToolCaller
from kos_core.llm.base import LLMClient
from kos_core.schemas.agents import AgentRequest, AgentResponse, Cost, EvidenceRef

SYSTEM_PROMPT = (
    "Eres KOS, un asistente que responde SOLO con la evidencia numerada que se te "
    "proporciona. Reglas estrictas:\n"
    "1. Responde en el mismo idioma que la pregunta.\n"
    "2. Cita cada afirmación con el marcador correspondiente entre corchetes, p. ej. [1].\n"
    "3. Usa TODA la evidencia relevante, aunque sea parcial o indirecta: si un fragmento "
    "menciona o describe algo relacionado con la pregunta, es información válida para "
    "responder con ella, incluso si no responde el 100% de la pregunta.\n"
    "4. Solo declara que no hay evidencia si NINGÚN fragmento se relaciona con la "
    "pregunta. Si la evidencia es parcial, responde con lo que sí cubre y aclara "
    "explícitamente qué falta — nunca te niegues a responder cuando hay evidencia "
    "relacionada disponible.\n"
    "5. No uses conocimiento externo a la evidencia: no inventes hechos que no estén en "
    "ella, pero sí puedes conectar/resumir lo que varios fragmentos dicen en conjunto.\n"
    "6. Si la pregunta pide una plantilla o estructura para crear algo: si algún fragmento "
    "de evidencia está marcado como (plantilla), cítalo tal cual existe — no lo combines "
    "con fragmentos marcados como (nota) para 'completarlo' o inventar secciones que no "
    "están en él. Si ningún fragmento es una plantilla, dilo explícitamente ('no encontré "
    "una plantilla existente para esto') en vez de construir una a partir de fragmentos "
    "sueltos.\n"
    "7. Nunca presentes como una sola entidad coherente (una plantilla, un proceso, una "
    "definición) contenido que proviene de documentos distintos y no relacionados entre "
    "sí: cada fragmento se cita por separado, con su propia fuente; no fusiones "
    "estructuras de fuentes distintas."
)

NO_EVIDENCE_ANSWER = (
    "No encontré evidencia en la base de conocimiento para responder a esa pregunta."
)


class SynthesisError(Exception):
    """El LLM de síntesis no pudo generar la respuesta. `apps/api` mapea esto a
    503; fallos de los pasos previos (retrieval/graph) NO son esto."""


def _build_context(evidence: list[EvidenceRef]) -> str:
    bloques = []
    for index, ref in enumerate(evidence, start=1):
        titulo = ref.title or ref.source_id or "sin título"
        tipo = "plantilla" if ref.doc_type == "template" else "nota"
        bloques.append(f"[{index}] ({titulo} · {tipo}) {ref.quote}")
    return "\n\n".join(bloques)


class WritingAgent:
    def __init__(self, llm: LLMClient, tool_caller: ToolCaller | None = None) -> None:
        self._llm = llm
        self._tool_caller = tool_caller

    def _require_tool_caller(self) -> ToolCaller:
        if self._tool_caller is None:
            raise RuntimeError("WritingAgent sin tool_caller: no puede operar sobre el vault")
        return self._tool_caller

    async def read_note(self, path: str, *, source_name: str | None = None, trace_id: str) -> str:
        result = await self._require_tool_caller().call_tool(
            "obsidian.read_note",
            {"path": path, "source_name": source_name, "confirm": True, "trace_id": trace_id},
        )
        content = result.get("content")
        if content is None:
            raise RuntimeError(result.get("message") or f"no se pudo leer {path!r}")
        return str(content)

    async def update_note(
        self, path: str, content: str, *, source_name: str | None = None, trace_id: str
    ) -> bool:
        result = await self._require_tool_caller().call_tool(
            "obsidian.update_note",
            {
                "path": path,
                "content": content,
                "source_name": source_name,
                "confirm": True,
                "trace_id": trace_id,
            },
        )
        return bool(result.get("approved") and result.get("path"))

    async def create_folder(
        self, path: str, *, source_name: str | None = None, trace_id: str
    ) -> bool:
        result = await self._require_tool_caller().call_tool(
            "obsidian.create_folder",
            {"path": path, "source_name": source_name, "confirm": True, "trace_id": trace_id},
        )
        return bool(result.get("approved") and result.get("path"))

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        query = str(request.inputs["query"])
        evidence_raw: Any = request.inputs.get("evidence", [])
        evidence = [
            ev if isinstance(ev, EvidenceRef) else EvidenceRef.model_validate(ev)
            for ev in evidence_raw
        ]
        confidence = float(request.inputs.get("confidence", 0.0))

        if not evidence:
            # Sin evidencia no se llama al LLM: no se permite alucinar (doc 06 §2).
            elapsed_ms = (time.perf_counter() - started) * 1000
            return AgentResponse(
                outputs={"answer": NO_EVIDENCE_ANSWER},
                evidence=[],
                confidence=0.0,
                cost=Cost(ms=elapsed_ms),
                trace_id=request.trace_id,
            )

        context = _build_context(evidence)
        prompt = (
            f"Pregunta: {query}\n\n"
            f"Evidencia disponible:\n{context}\n\n"
            "Responde a la pregunta usando solo la evidencia anterior y citando con [n]."
        )
        try:
            answer = await self._llm.generate(
                prompt, system=SYSTEM_PROMPT, timeout=request.constraints.timeout_s
            )
        except Exception as exc:  # solo la síntesis; los pasos previos ya terminaron
            raise SynthesisError(str(exc)) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000
        return AgentResponse(
            outputs={"answer": answer},
            evidence=evidence,
            confidence=confidence,
            cost=Cost(ms=elapsed_ms),
            trace_id=request.trace_id,
        )
