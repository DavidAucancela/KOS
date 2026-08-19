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

// Trae las últimas 100 recomendaciones de cualquier estado (mejora de
// interfaz posterior a Sprint 25, doc 11 §7/§8): un solo fetch sin filtrar
// por status, el filtrado pendiente/historial se hace en el componente —
// suficiente para un vault de un solo usuario con el tope de generación por
// pasada ya existente (`recommend.py`); paginar de verdad solo haría falta
// a un volumen que hoy no existe.
export function useRecommendations(): UseRecommendationsResult {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/v1/recommendations?limit=100");
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
    void fetchAll();
  }, [fetchAll]);

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
      const updated = (await response.json()) as Recommendation;
      // Actualiza el ítem en el lugar (no lo saca de la lista): pasa de
      // "pendiente" a aparecer en el historial sin un refetch completo.
      setItems((current) =>
        current.map((item) => (item.recommendation_id === id ? updated : item)),
      );
    },
    [],
  );

  return { items, loading, error, resolve };
}
