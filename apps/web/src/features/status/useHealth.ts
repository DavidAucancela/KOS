import { useEffect, useState } from "react";

import type { HealthResponse } from "./types";

const POLL_INTERVAL_MS = 5000;

export interface UseHealthResult {
  data: HealthResponse | null;
  error: string | null;
  lastUpdated: Date | null;
}

// Consulta GET /health (proxy de Vite → apps/api) con polling.
// Si la API no responde, expone `error` y conserva el último estado conocido.
export function useHealth(): UseHealthResult {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchHealth() {
      try {
        const response = await fetch("/health");
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const body = (await response.json()) as HealthResponse;
        if (cancelled) return;
        setData(body);
        setError(null);
        setLastUpdated(new Date());
      } catch (cause) {
        if (cancelled) return;
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    }

    void fetchHealth();
    const timer = setInterval(() => void fetchHealth(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return { data, error, lastUpdated };
}
