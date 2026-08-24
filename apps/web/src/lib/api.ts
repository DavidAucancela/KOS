// Mensaje legible de un fetch que falló, a partir del `{detail}` de FastAPI
// (RFC 9457) si lo trae, o del status HTTP si no. Extraído de `usePlan.ts`/
// `useRecommendations.ts` (doc 06 §2 addendum 2026-08-21, plan de Métricas):
// vive en lib/ porque doc 10 §4 prohíbe que una feature importe de otra.
export async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // el body no era JSON (o no traía `detail`) — se usa el status.
  }
  return `HTTP ${response.status}`;
}
