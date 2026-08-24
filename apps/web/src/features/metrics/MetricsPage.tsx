import { useMemo, useState } from "react";
import { AlertCircle, AlertTriangle, Info, Table2, TrendingDown, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageContainer, PageHeader } from "@/components/page";
import { DEGRADED_REASON_LABEL } from "@/lib/degradedReasons";
import { cn } from "@/lib/utils";
import type { AgentDistribution, Insight, LatencyBucket, SinceRange } from "./types";
import { useMetrics } from "./useMetrics";

const RANGES: { value: SinceRange; label: string }[] = [
  { value: 24, label: "24h" },
  { value: 168, label: "7d" },
  { value: 720, label: "30d" },
];

// Color fijo por agente (paleta categórica validada, ver docs/plan y
// apps/web/src/index.css) — nunca reordenado por valor.
const AGENT_COLOR: Record<string, string> = {
  retrieval: "var(--chart-agent-1)",
  graph: "var(--chart-agent-2)",
  research: "var(--chart-agent-3)",
  memory: "var(--chart-agent-4)",
  writing: "var(--chart-agent-5)",
  learning: "var(--chart-agent-6)",
};
const FALLBACK_AGENT_COLORS = Object.values(AGENT_COLOR);

function agentColor(agent: string, indexIfUnknown: number): string {
  return AGENT_COLOR[agent] ?? FALLBACK_AGENT_COLORS[indexIfUnknown % FALLBACK_AGENT_COLORS.length];
}

const SEVERITY_STYLE: Record<Insight["severity"], { icon: typeof Info; className: string }> = {
  info: { icon: Info, className: "border-primary/30 bg-primary/10 text-primary" },
  warning: { icon: AlertTriangle, className: "border-warning/30 bg-warning/10 text-warning" },
  critical: {
    icon: AlertCircle,
    className: "border-destructive/30 bg-destructive/10 text-destructive",
  },
};

function InsightsRow({ insights }: { insights: Insight[] }) {
  if (insights.length === 0) return null;
  return (
    <div className="space-y-2">
      {insights.map((insight, i) => {
        const { icon: Icon, className } = SEVERITY_STYLE[insight.severity];
        return (
          <div
            key={i}
            className={cn(
              "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
              className,
            )}
          >
            <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>{insight.message}</span>
          </div>
        );
      })}
    </div>
  );
}

// `higherIsBad`: para latencia/degradación/tokens, subir es la dirección que
// se resalta en rojo; para "total de planes" no aplica juicio de valor.
function Trend({
  current,
  previous,
  higherIsBad,
}: {
  current: number;
  previous: number | undefined;
  higherIsBad: boolean;
}) {
  if (previous === undefined || previous === 0) return null;
  const deltaPct = ((current - previous) / previous) * 100;
  if (Math.abs(deltaPct) < 1) return null;
  const up = deltaPct > 0;
  const bad = higherIsBad ? up : !up;
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-medium",
        bad ? "text-destructive" : "text-success",
      )}
    >
      <Icon className="size-3" aria-hidden />
      {Math.abs(deltaPct).toFixed(0)}%
    </span>
  );
}

function StatTile({
  label,
  value,
  current,
  previous,
  higherIsBad,
}: {
  label: string;
  value: string;
  current: number;
  previous: number | undefined;
  higherIsBad: boolean;
}) {
  return (
    <Card>
      <CardContent className="space-y-1 p-4">
        <p className="text-muted-foreground text-xs">{label}</p>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-semibold tabular-nums">{value}</span>
          <Trend current={current} previous={previous} higherIsBad={higherIsBad} />
        </div>
      </CardContent>
    </Card>
  );
}

const CHART_WIDTH = 640;
const CHART_HEIGHT = 160;
const CHART_PAD = 8;

function LatencyChart({ buckets }: { buckets: LatencyBucket[] }) {
  const [tableView, setTableView] = useState(false);
  const [hover, setHover] = useState<number | null>(null);

  const points = useMemo(() => {
    if (buckets.length === 0) return [];
    const maxMs = Math.max(...buckets.map((b) => b.avg_ms), 1);
    const innerWidth = CHART_WIDTH - CHART_PAD * 2;
    const innerHeight = CHART_HEIGHT - CHART_PAD * 2;
    return buckets.map((b, i) => {
      const x =
        CHART_PAD + (buckets.length === 1 ? innerWidth / 2 : (i / (buckets.length - 1)) * innerWidth);
      const y = CHART_PAD + innerHeight - (b.avg_ms / maxMs) * innerHeight;
      return { x, y, bucket: b };
    });
  }, [buckets]);

  if (buckets.length === 0) {
    return <p className="text-muted-foreground text-sm">Sin datos de latencia en este rango.</p>;
  }

  // Un solo bucket degenera un <path> a un "M" sin "L" (no dibuja nada): se
  // traza como una línea horizontal plana a todo el ancho para que igual se
  // vea una marca, sin inventar buckets — el tooltip sigue usando el punto
  // real (`points`, no `pathPoints`) para mostrar el momento correcto.
  const pathPoints =
    points.length === 1
      ? [
          { x: CHART_PAD, y: points[0].y },
          { x: CHART_WIDTH - CHART_PAD, y: points[0].y },
        ]
      : points;
  const linePath = pathPoints.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const areaPath = `${linePath} L${pathPoints[pathPoints.length - 1].x},${CHART_HEIGHT - CHART_PAD} L${pathPoints[0].x},${CHART_HEIGHT - CHART_PAD} Z`;
  const hovered = hover !== null ? points[hover] : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Latencia en el tiempo</p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-1.5 text-xs"
          onClick={() => setTableView((v) => !v)}
        >
          <Table2 className="size-3.5" aria-hidden />
          {tableView ? "Ver gráfico" : "Ver como tabla"}
        </Button>
      </div>

      {tableView ? (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-xs">
            <thead className="text-muted-foreground border-b border-border">
              <tr>
                <th className="px-3 py-1.5 text-left font-medium">Momento</th>
                <th className="px-3 py-1.5 text-right font-medium">Latencia promedio</th>
                <th className="px-3 py-1.5 text-right font-medium">Planes</th>
              </tr>
            </thead>
            <tbody>
              {buckets.map((b) => (
                <tr key={b.bucket} className="border-b border-border/50 last:border-0">
                  <td className="px-3 py-1.5">{new Date(b.bucket).toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{b.avg_ms.toFixed(0)} ms</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{b.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            className="w-full"
            role="img"
            aria-label="Latencia promedio del Planner en el tiempo"
            onMouseLeave={() => setHover(null)}
            onMouseMove={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              const relX = ((event.clientX - rect.left) / rect.width) * CHART_WIDTH;
              let nearest = 0;
              let best = Infinity;
              points.forEach((p, i) => {
                const d = Math.abs(p.x - relX);
                if (d < best) {
                  best = d;
                  nearest = i;
                }
              });
              setHover(nearest);
            }}
          >
            <defs>
              <linearGradient id="latency-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.25} />
                <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <path d={areaPath} fill="url(#latency-fill)" stroke="none" />
            <path
              d={linePath}
              fill="none"
              stroke="var(--primary)"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {points.length <= 8 &&
              points.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r={2.5} fill="var(--primary)" />
              ))}
            {hovered && (
              <>
                <line
                  x1={hovered.x}
                  x2={hovered.x}
                  y1={CHART_PAD}
                  y2={CHART_HEIGHT - CHART_PAD}
                  stroke="var(--border)"
                  strokeWidth={1}
                />
                <circle cx={hovered.x} cy={hovered.y} r={3.5} fill="var(--primary)" />
              </>
            )}
          </svg>
          {hovered && (
            <div
              className="border-border bg-card pointer-events-none absolute top-1 -translate-x-1/2 rounded-md border px-2 py-1 text-xs shadow-sm"
              style={{ left: `${(hovered.x / CHART_WIDTH) * 100}%` }}
            >
              <p className="font-medium">{new Date(hovered.bucket.bucket).toLocaleString()}</p>
              <p className="text-muted-foreground">
                {hovered.bucket.avg_ms.toFixed(0)} ms · {hovered.bucket.count} plan
                {hovered.bucket.count === 1 ? "" : "es"}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DegradationBars({
  items,
  total,
}: {
  items: { reason: string | null; count: number }[];
  total: number;
}) {
  if (items.length === 0) {
    return <p className="text-muted-foreground text-sm">Sin degradaciones en este rango.</p>;
  }
  return (
    <div className="space-y-2">
      {items.map((item) => {
        const pct = total > 0 ? (item.count / total) * 100 : 0;
        const label = item.reason ? (DEGRADED_REASON_LABEL[item.reason] ?? item.reason) : "Sin razón";
        return (
          <div key={item.reason ?? "none"} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{label}</span>
              <span className="tabular-nums">
                {item.count} ({pct.toFixed(0)}%)
              </span>
            </div>
            <div className="bg-muted h-2 overflow-hidden rounded-full">
              <div
                className="bg-destructive h-full rounded-full"
                style={{ width: `${Math.max(pct, 2)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AgentDistributionBars({ items }: { items: AgentDistribution[] }) {
  if (items.length === 0) {
    return <p className="text-muted-foreground text-sm">Sin pasos ejecutados en este rango.</p>;
  }
  const total = items.reduce((sum, item) => sum + item.count, 0);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {items.map((item, i) => (
          <span key={item.agent} className="flex items-center gap-1.5 text-xs">
            <span
              className="size-2.5 rounded-full"
              style={{ backgroundColor: agentColor(item.agent, i) }}
              aria-hidden
            />
            {item.agent}
          </span>
        ))}
      </div>
      <div className="space-y-2">
        {items.map((item, i) => {
          const pct = total > 0 ? (item.count / total) * 100 : 0;
          return (
            <div key={item.agent} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium">{item.agent}</span>
                <span className="text-muted-foreground tabular-nums">
                  {item.count} ({pct.toFixed(0)}%)
                </span>
              </div>
              <div className="bg-muted h-2 overflow-hidden rounded-full">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.max(pct, 2)}%`, backgroundColor: agentColor(item.agent, i) }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms.toFixed(0)} ms`;
}

export function MetricsPage() {
  const [range, setRange] = useState<SinceRange>(24);
  const { metrics, loading, error } = useMetrics(range);

  return (
    <PageContainer wide>
      <PageHeader
        title="KOS — Métricas del Planner"
        description="Latencia, degradación, distribución de agentes y tokens agregados en el tiempo (doc 09 §6)."
        actions={
          <div className="flex gap-1 rounded-md border border-border p-0.5">
            {RANGES.map((r) => (
              <Button
                key={r.value}
                type="button"
                size="sm"
                variant={range === r.value ? "default" : "ghost"}
                onClick={() => setRange(r.value)}
              >
                {r.label}
              </Button>
            ))}
          </div>
        }
      />

      {error && (
        <p className="border-destructive/30 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">
          {error}
        </p>
      )}

      {loading && !metrics && <p className="text-muted-foreground text-sm">Cargando métricas…</p>}

      {metrics && (
        <div className="space-y-6">
          <InsightsRow insights={metrics.insights} />

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Planes ejecutados"
              value={String(metrics.current_period.total_plans)}
              current={metrics.current_period.total_plans}
              previous={metrics.previous_period?.total_plans}
              higherIsBad={false}
            />
            <StatTile
              label="Tasa de degradación"
              value={`${(metrics.current_period.degradation_rate * 100).toFixed(0)}%`}
              current={metrics.current_period.degradation_rate}
              previous={metrics.previous_period?.degradation_rate}
              higherIsBad
            />
            <StatTile
              label="Latencia promedio"
              value={fmtMs(metrics.current_period.avg_latency_ms)}
              current={metrics.current_period.avg_latency_ms}
              previous={metrics.previous_period?.avg_latency_ms}
              higherIsBad
            />
            <StatTile
              label="Tokens totales"
              value={metrics.current_period.total_tokens.toLocaleString()}
              current={metrics.current_period.total_tokens}
              previous={metrics.previous_period?.total_tokens}
              higherIsBad={false}
            />
          </div>

          <Card>
            <CardContent className="p-4">
              <LatencyChart buckets={metrics.latency} />
            </CardContent>
          </Card>

          <div className="grid gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Degradación por razón</CardTitle>
              </CardHeader>
              <CardContent>
                <DegradationBars
                  items={metrics.degradation_by_reason}
                  total={metrics.current_period.degraded_plans}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Distribución de agentes</CardTitle>
              </CardHeader>
              <CardContent>
                <AgentDistributionBars items={metrics.agent_distribution} />
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
