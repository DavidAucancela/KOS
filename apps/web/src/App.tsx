import { useState } from "react";
import { Activity, LineChart, ListTree, MessagesSquare, Network } from "lucide-react";

import { cn } from "@/lib/utils";
import { ChatPage } from "./features/chat/ChatPage";
import { GraphPage } from "./features/graph/GraphPage";
import { MetricsPage } from "./features/metrics/MetricsPage";
import { useRecommendations } from "./features/recommendations/useRecommendations";
import { StatusPage } from "./features/status/StatusPage";
import { TracesPage } from "./features/traces/TracesPage";

// Shell de la app: semilla del layout IDE del doc 10 §4. Chat, Grafo, Trazas
// (Sprint 19), Estado, y Métricas (doc 06 §2 addendum 2026-08-21).
type View = "chat" | "graph" | "traces" | "status" | "metrics";

const NAV: { id: View; label: string; icon: typeof Activity }[] = [
  { id: "chat", label: "Chat", icon: MessagesSquare },
  { id: "graph", label: "Grafo", icon: Network },
  { id: "traces", label: "Trazas", icon: ListTree },
  { id: "status", label: "Estado", icon: Activity },
  { id: "metrics", label: "Métricas", icon: LineChart },
];

export default function App() {
  const [view, setView] = useState<View>("chat");
  // Sprint 19: "ver plan" en el chat navega acá con un plan_id preseleccionado.
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  // Badge de conteo en "Estado" (mejora de interfaz posterior a Sprint 25,
  // doc 11 §7): mismo hook que usa RecommendationsPanel, sin mecanismo de
  // conteo nuevo — el fetch se hace una vez al montar el shell.
  const { items: recommendations } = useRecommendations();
  const pendingCount = recommendations.filter((item) => item.status === "pending").length;

  return (
    <div className="flex h-screen">
      <nav className="flex w-14 shrink-0 flex-col items-center gap-1 border-r border-border py-3">
        {NAV.map(({ id, label, icon: Icon }) => {
          const showBadge = id === "status" && pendingCount > 0;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setView(id)}
              title={label}
              aria-label={showBadge ? `${label} (${pendingCount} recomendaciones pendientes)` : label}
              aria-current={view === id}
              className={cn(
                "relative flex size-10 items-center justify-center rounded-md",
                view === id ? "bg-muted text-primary" : "text-muted-foreground hover:bg-muted",
              )}
            >
              <Icon className="size-5" aria-hidden />
              {showBadge && (
                <span className="bg-primary text-primary-foreground absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-medium">
                  {pendingCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {view === "chat" && (
          <ChatPage
            onViewPlan={(planId) => {
              setSelectedPlanId(planId);
              setView("traces");
            }}
          />
        )}
        {view === "graph" && <GraphPage />}
        {view === "traces" && <TracesPage initialPlanId={selectedPlanId} />}
        {view === "status" && <StatusPage />}
        {view === "metrics" && <MetricsPage />}
      </div>
    </div>
  );
}
