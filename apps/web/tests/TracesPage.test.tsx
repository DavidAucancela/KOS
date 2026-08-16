import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TracesPage } from "../src/features/traces/TracesPage";
import type { PlanOut } from "../src/features/traces/types";

function plan(overrides: Partial<PlanOut> = {}): PlanOut {
  return {
    plan_id: "plan-1",
    query: "¿qué es KOS?",
    steps: [
      {
        id: "s1",
        agent: "retrieval",
        task: "buscar evidencia",
        inputs: {},
        depends_on: [],
        evidence_count: 2,
        confidence: 0.6,
        cost: { tokens: 0, ms: 12.5 },
      },
      {
        id: "s2",
        agent: "writing",
        task: "redactar",
        inputs: {},
        depends_on: ["s1"],
        evidence_count: null,
        confidence: null,
        cost: null,
      },
    ],
    degraded: false,
    degraded_reason: null,
    elapsed_ms: 42,
    trace_id: "trace-1",
    created_at: "2026-08-16T00:00:00Z",
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TracesPage", () => {
  it("carga y muestra los pasos de un plan preseleccionado", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(plan())));

    render(<TracesPage initialPlanId="plan-1" />);

    expect(await screen.findByText("¿qué es KOS?")).toBeInTheDocument();
    expect(screen.getByText("retrieval")).toBeInTheDocument();
    expect(screen.getByText("writing")).toBeInTheDocument();
  });

  it("muestra el motivo de degradación cuando el plan se degradó", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(plan({ degraded: true, degraded_reason: "budget_timeout" })),
      ),
    );

    render(<TracesPage initialPlanId="plan-1" />);

    expect(await screen.findByText(/Plan degradado/)).toBeInTheDocument();
    expect(screen.getByText(/presupuesto de tiempo/)).toBeInTheDocument();
  });

  it("muestra un mensaje de error si el plan no existe (404)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Plan no encontrado" }, 404)),
    );

    render(<TracesPage initialPlanId="plan-inexistente" />);

    expect(await screen.findByText("Plan no encontrado")).toBeInTheDocument();
  });

  it("sin plan preseleccionado muestra el mensaje inicial", () => {
    render(<TracesPage initialPlanId={null} />);

    expect(screen.getByText(/Pegá un plan_id/)).toBeInTheDocument();
  });
});
