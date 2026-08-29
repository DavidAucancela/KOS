"""Métricas agregadas del Planner en el tiempo (doc 06 §2 addendum 2026-08-21,
cierra el hueco de doc 09 §6 registrado en `docs/deuda-tecnica.md` "Monitoreo").

`compute_insights` son reglas estadísticas deterministas (comparación contra el
período anterior de igual duración) — no invocan al LLM ni al Planner. No aplica
ni viola la regla 3 de CLAUDE.md ("el LLM nunca accede a datos directamente")
porque ningún LLM participa; es aritmética sobre agregados SQL ya calculados.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

InsightSeverity = Literal["info", "warning", "critical"]
InsightMetric = Literal["latency", "degradation", "agent_distribution", "tokens"]

# Umbrales iniciales, sin tuning contra uso real (mismo espíritu que
# SIMILARITY_THRESHOLD u otros umbrales del proyecto — valores conservadores de
# partida, no un análisis estadístico afinado).
_DEGRADATION_CRITICAL_RATE = 0.15
_DEGRADATION_WARNING_DELTA_PP = 10.0
_LATENCY_WARNING_DELTA_PCT = 20.0
_AGENT_DOMINANCE_SHARE = 0.6
_TOKENS_INFO_DELTA_PCT = 30.0


class PeriodSummary(BaseModel):
    total_plans: int
    degraded_plans: int
    degradation_rate: float
    avg_latency_ms: float
    total_tokens: int


class LatencyBucket(BaseModel):
    bucket: datetime
    avg_ms: float
    count: int


class DegradationBreakdown(BaseModel):
    reason: str | None
    count: int


class AgentDistribution(BaseModel):
    agent: str
    count: int


class AgentLatency(BaseModel):
    """Promedio de `cost.ms` por agente sobre los pasos con costo registrado
    (doc 06 §2 addendum: `agent_distribution` ya contaba pasos por agente,
    pero no si `research`/`memory` es sistemáticamente el cuello de botella —
    `count` acá es la cantidad de pasos con `cost.ms` presente, no el total de
    pasos de ese agente)."""

    agent: str
    avg_ms: float
    count: int


class Insight(BaseModel):
    severity: InsightSeverity
    metric: InsightMetric
    message: str
    delta_pct: float | None = None


class PlanMetrics(BaseModel):
    since: datetime
    current_period: PeriodSummary
    previous_period: PeriodSummary | None
    latency: list[LatencyBucket]
    degradation_by_reason: list[DegradationBreakdown]
    agent_distribution: list[AgentDistribution]
    agent_latency: list[AgentLatency]
    insights: list[Insight]


def compute_insights(
    *,
    current: PeriodSummary,
    previous: PeriodSummary | None,
    agent_distribution: list[AgentDistribution],
) -> list[Insight]:
    """Como máximo un `Insight` por regla; sin datos en el período actual o sin
    período anterior comparable, la regla correspondiente se omite en vez de
    dividir por cero o inventar un insight falso."""
    insights: list[Insight] = []
    if current.total_plans == 0:
        return insights

    if current.degradation_rate > _DEGRADATION_CRITICAL_RATE:
        insights.append(
            Insight(
                severity="critical",
                metric="degradation",
                message=(
                    f"La tasa de degradación está en {current.degradation_rate:.0%}, "
                    f"por encima del umbral de {_DEGRADATION_CRITICAL_RATE:.0%}."
                ),
            )
        )
    elif previous is not None and previous.total_plans > 0:
        delta_pp = (current.degradation_rate - previous.degradation_rate) * 100
        if delta_pp > _DEGRADATION_WARNING_DELTA_PP:
            insights.append(
                Insight(
                    severity="warning",
                    metric="degradation",
                    message=(
                        f"La tasa de degradación subió {delta_pp:.0f} puntos porcentuales "
                        "respecto al período anterior."
                    ),
                    delta_pct=delta_pp,
                )
            )

    if previous is not None and previous.total_plans > 0 and previous.avg_latency_ms > 0:
        latency_delta_pct = (
            (current.avg_latency_ms - previous.avg_latency_ms) / previous.avg_latency_ms * 100
        )
        if latency_delta_pct > _LATENCY_WARNING_DELTA_PCT:
            insights.append(
                Insight(
                    severity="warning",
                    metric="latency",
                    message=(
                        f"La latencia promedio subió {latency_delta_pct:.0f}% "
                        "respecto al período anterior."
                    ),
                    delta_pct=latency_delta_pct,
                )
            )
        elif latency_delta_pct < -_LATENCY_WARNING_DELTA_PCT:
            insights.append(
                Insight(
                    severity="info",
                    metric="latency",
                    message=(
                        f"La latencia promedio bajó {abs(latency_delta_pct):.0f}% "
                        "respecto al período anterior."
                    ),
                    delta_pct=latency_delta_pct,
                )
            )

    total_agent_steps = sum(item.count for item in agent_distribution)
    if total_agent_steps > 0:
        dominant = max(agent_distribution, key=lambda item: item.count)
        share = dominant.count / total_agent_steps
        if share > _AGENT_DOMINANCE_SHARE:
            insights.append(
                Insight(
                    severity="info",
                    metric="agent_distribution",
                    message=(
                        f"El agente '{dominant.agent}' concentra el {share:.0%} "
                        "de los pasos ejecutados en este período."
                    ),
                )
            )

    if previous is not None and previous.total_tokens > 0:
        tokens_delta_pct = (
            (current.total_tokens - previous.total_tokens) / previous.total_tokens * 100
        )
        if tokens_delta_pct > _TOKENS_INFO_DELTA_PCT:
            insights.append(
                Insight(
                    severity="info",
                    metric="tokens",
                    message=(
                        f"El consumo de tokens subió {tokens_delta_pct:.0f}% "
                        "respecto al período anterior."
                    ),
                    delta_pct=tokens_delta_pct,
                )
            )

    return insights
