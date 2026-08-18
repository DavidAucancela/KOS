import { useCallback, useEffect, useState } from "react";

import type { Recommendation } from "./types";

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // el body no era JSON (o no traía `detail`) — se usa el status.
  }
  return `HTTP ${response.status}`;
}

export interface UseRecommendationsResult {
  items: Recommendation[];
  loading: boolean;
  error: string | null;
  resolve: (id: string, status: "accepted" | "dismissed", reason?: string) => Promise<void>;
}

// Superficie mínima de recomendaciones pendientes (doc 11 §7, Sprint 25):
// lista + aceptar/descartar contra /v1/recommendations (proxy de Vite →
// apps/api), mismo patrón de fetch directo que `useHealth`/`usePlan`.
export function useRecommendations(): UseRecommendationsResult {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/v1/recommendations?status=pending");
      if (!response.ok) {
        setError(await errorMessage(response));
        return;
      }
      const body = (await response.json()) as { items?: Recommendation[] };
      setItems(Array.isArray(body.items) ? body.items : []);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchPending();
  }, [fetchPending]);

  const resolve = useCallback(
    async (id: string, status: "accepted" | "dismissed", reason?: string) => {
      const response = await fetch(`/v1/recommendations/${encodeURIComponent(id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, reason }),
      });
      if (!response.ok) {
        setError(await errorMessage(response));
        return;
      }
      // Quita la recomendación resuelta de la lista sin esperar un refetch
      // completo — misma UX que "optimistic update" sin ser optimista de
      // verdad (la respuesta del PATCH ya confirmó el cambio real).
      setItems((current) => current.filter((item) => item.recommendation_id !== id));
    },
    [],
  );

  return { items, loading, error, resolve };
}
