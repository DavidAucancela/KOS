import { useCallback, useState } from "react";

import type { QueryResponse } from "./types";

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
  ask: (query: string) => Promise<void>;
}

// Mensaje legible por humano según el fallo del POST /v1/query.
function errorMessage(status: number): string {
  if (status === 503) {
    return "El modelo de lenguaje (Ollama) no está disponible ahora mismo.";
  }
  return `La consulta falló (HTTP ${status}).`;
}

// Conversación contra POST /v1/query (proxy de Vite → apps/api). Mantiene el
// historial de turnos; un fallo de red o 503 se muestra como error del turno,
// nunca rompe la UI.
export function useChat(): UseChatResult {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);

  const ask = useCallback(async (query: string) => {
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
        body: JSON.stringify({ query: trimmed }),
      });
      if (!response.ok) {
        settle({ error: errorMessage(response.status) });
        return;
      }
      const body = (await response.json()) as QueryResponse;
      settle({ response: body });
    } catch (cause) {
      settle({ error: cause instanceof Error ? cause.message : String(cause) });
    } finally {
      setBusy(false);
    }
  }, []);

  return { turns, busy, ask };
}
