// Etiquetas humanas de `degraded_reason` (doc 03 §3 regla 4, doc 09 §6).
// Compartido entre features/traces y features/metrics — vive en lib/ porque
// doc 10 §4 prohíbe que una feature importe de otra directamente.
export const DEGRADED_REASON_LABEL: Record<string, string> = {
  llm_generation: "El LLM no generó un plan válido tras reintentar",
  step_failure: "Un paso individual falló y degradó a evidencia parcial",
  budget_timeout: "Se cortó por presupuesto de tiempo (timeout_s)",
  budget_max_steps: "El plan generado excedía el máximo de pasos permitido",
};
