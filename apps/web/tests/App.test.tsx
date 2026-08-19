import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import type { Recommendation } from "../src/features/recommendations/types";

function recommendation(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    recommendation_id: "rec-1",
    type: "gap",
    title: "Posible laguna: Docker",
    description: "",
    evidence: [],
    target_entities: ["node-1"],
    confidence: 0.7,
    priority: 1,
    status: "pending",
    dismissed_reason: null,
    source_event_id: "trace-1",
    created_at: "2026-08-17T00:00:00Z",
    resolved_at: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: () => Promise.resolve(body) } as unknown as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App — badge de recomendaciones pendientes en el nav", () => {
  it("muestra la cantidad de pendientes sobre el ícono Estado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          items: [recommendation(), recommendation({ recommendation_id: "rec-2" })],
          next_cursor: null,
        }),
      ),
    );

    render(<App />);

    expect(await screen.findByText("2")).toBeInTheDocument();
    expect(screen.getByLabelText("Estado (2 recomendaciones pendientes)")).toBeInTheDocument();
  });

  it("no muestra badge cuando no hay recomendaciones pendientes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ items: [], next_cursor: null })),
    );

    render(<App />);

    // Deja que el fetch inicial resuelva antes de asegurar la ausencia del badge.
    await screen.findByLabelText("Estado");
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("no cuenta recomendaciones ya resueltas en el badge", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          items: [recommendation({ status: "accepted" })],
          next_cursor: null,
        }),
      ),
    );

    render(<App />);

    await screen.findByLabelText("Estado");
    expect(screen.queryByLabelText(/recomendaciones pendientes/)).not.toBeInTheDocument();
  });
});
