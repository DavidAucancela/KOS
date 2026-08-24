// Tipos del contrato GET /v1/plans/metrics (doc 06 §2 addendum 2026-08-21),
// derivados del cliente generado desde OpenAPI. Regla doc 09 §3: los tipos de
// la API no se escriben a mano.

import type { components } from "../../api/schema";

export type PlanMetricsOut = components["schemas"]["PlanMetricsOut"];
export type PeriodSummary = components["schemas"]["PeriodSummary"];
export type LatencyBucket = components["schemas"]["LatencyBucket"];
export type DegradationBreakdown = components["schemas"]["DegradationBreakdown"];
export type AgentDistribution = components["schemas"]["AgentDistribution"];
export type Insight = components["schemas"]["Insight"];

export type SinceRange = 24 | 168 | 720; // 24h / 7d / 30d, en horas
