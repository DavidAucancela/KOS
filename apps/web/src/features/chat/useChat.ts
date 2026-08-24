import { useCallback, useState } from "react";

import type { ConversationDetail, MessageOut, QueryResponse } from "./types";

export interface ChatTurn {
  id: number;
  question: string;
  pending: boolean;
  response: QueryResponse | null;
  error: string | null;
}

export interface UseChatResult {
  turns: ChatTurn[];
  busy: boolean;
  conversationId: string | null;
  ask: (query: string) => Promise<void>;
  loadConversation: (conversationId: string) => Promise<void>;
  newConversation: () => void;
}

// Mensaje legible por humano según el fallo del POST /v1/query.
function errorMessage(status: number): string {
  if (status === 503) {
    return "El modelo de lenguaje (Ollama) no está disponible ahora mismo.";
  }
  return `La consulta falló (HTTP ${status}).`;
}

// Empareja mensajes user/assistant consecutivos de una conversación cargada
// (doc 06 §2 addendum 2026-08-21) en la misma forma `ChatTurn[]` que ya usa
// `AssistantTurn` — no hace falta un shape nuevo para el historial persistido.
function turnsFromMessages(messages: MessageOut[], conversationId: string): ChatTurn[] {
  const turns: ChatTurn[] = [];
  for (let i = 0; i < messages.length; i += 1) {
    const message = messages[i];
    if (message.role !== "user") continue;
    const next = messages[i + 1];
    const response: QueryResponse | null =
      next && next.role === "assistant"
        ? {
            query: message.content,
            answer: next.content,
            evidence: next.evidence,
            confidence: next.confidence ?? 0,
            plan: [],
            degraded: next.degraded,
            trace_id: "",
            plan_id: next.plan_id ?? "",
            conversation_id: conversationId,
          }
        : null;
    turns.push({
      id: turns.length,
      question: message.content,
      pending: false,
      response,
      error: null,
    });
  }
  return turns;
}

// Conversación contra POST /v1/query (proxy de Vite → apps/api). Mantiene el
// historial de turnos; un fallo de red o 503 se muestra como error del turno,
// nunca rompe la UI. Desde el addendum 2026-08-21, el historial se persiste en
// servidor: `conversationId` viaja en cada request y se adopta de la respuesta
// (auto-creada la primera vez que se pregunta algo).
export function useChat(): UseChatResult {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const ask = useCallback(
    async (query: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;

      const id = Date.now();
      setTurns((prev) => [
        ...prev,
        { id, question: trimmed, pending: true, response: null, error: null },
      ]);
      setBusy(true);

      const settle = (patch: Partial<ChatTurn>) =>
        setTurns((prev) =>
          prev.map((turn) => (turn.id === id ? { ...turn, pending: false, ...patch } : turn)),
        );

      try {
        const response = await fetch("/v1/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: trimmed, conversation_id: conversationId }),
        });
        if (!response.ok) {
          settle({ error: errorMessage(response.status) });
          return;
        }
        const body = (await response.json()) as QueryResponse;
        settle({ response: body });
        setConversationId(body.conversation_id);
      } catch (cause) {
        settle({ error: cause instanceof Error ? cause.message : String(cause) });
      } finally {
        setBusy(false);
      }
    },
    [conversationId],
  );

  const loadConversation = useCallback(async (id: string) => {
    const response = await fetch(`/v1/conversations/${encodeURIComponent(id)}`);
    if (!response.ok) return;
    const detail = (await response.json()) as ConversationDetail;
    setTurns(turnsFromMessages(detail.messages, detail.conversation.conversation_id));
    setConversationId(detail.conversation.conversation_id);
  }, []);

  const newConversation = useCallback(() => {
    setTurns([]);
    setConversationId(null);
  }, []);

  return { turns, busy, conversationId, ask, loadConversation, newConversation };
}
