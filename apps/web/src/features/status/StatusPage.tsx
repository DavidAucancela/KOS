import type { LucideIcon } from "lucide-react";
import { Boxes, Brain, Database, HardDrive, Share2, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageContainer, PageHeader } from "@/components/page";
import { MemoryProposalsPanel } from "../memory-proposals/MemoryProposalsPanel";
import { RecommendationsPanel } from "../recommendations/RecommendationsPanel";
import type { ServiceStatus } from "./types";
import { useHealth } from "./useHealth";

const SERVICE_ICONS: Record<string, LucideIcon> = {
  postgres: Database,
  neo4j: Share2,
  redis: Zap,
  minio: HardDrive,
  ollama: Brain,
};

function GlobalBadge({ apiError, status }: { apiError: string | null; status?: "ok" | "degraded" }) {
  if (apiError) return <Badge variant="destructive">API inaccesible</Badge>;
  if (status === "ok") return <Badge variant="success">Operativo</Badge>;
  if (status === "degraded") return <Badge variant="destructive">Degradado</Badge>;
  return <Badge variant="outline">Conectando…</Badge>;
}

function ServiceCard({ name, service }: { name: string; service: ServiceStatus }) {
  const Icon = SERVICE_ICONS[name] ?? Boxes;
  const ok = service.status === "ok";
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Icon className="text-muted-foreground size-4" aria-hidden />
          {name}
        </CardTitle>
        <Badge variant={ok ? "success" : "destructive"}>{service.status}</Badge>
      </CardHeader>
      <CardContent className="space-y-1">
        <p className="text-muted-foreground text-xs">latencia: {service.latency_ms.toFixed(1)} ms</p>
        {service.detail && <p className="text-destructive text-xs">{service.detail}</p>}
      </CardContent>
    </Card>
  );
}

export function StatusPage() {
  const { data, error, lastUpdated } = useHealth();

  return (
    <PageContainer>
      <PageHeader
        title="KOS — Estado del sistema"
        actions={<GlobalBadge apiError={error} status={data?.status} />}
      />

      {error && (
        <p className="border-destructive/30 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">
          No se pudo consultar la API ({error}). ¿Está corriendo <code>make dev</code>?
        </p>
      )}

      {data && (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Object.entries(data.services).map(([name, service]) => (
            <ServiceCard key={name} name={name} service={service} />
          ))}
        </section>
      )}

      <RecommendationsPanel />

      <MemoryProposalsPanel />

      <footer className="text-muted-foreground mt-auto text-xs">
        {lastUpdated
          ? `Última actualización: ${lastUpdated.toLocaleTimeString()}`
          : "Sin datos todavía"}
      </footer>
    </PageContainer>
  );
}
