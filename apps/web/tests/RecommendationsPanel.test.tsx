import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecommendationsPanel } from "../src/features/recommendations/RecommendationsPanel";
import type { Recommendation } from "../src/features/recommendations/types";

function recommendation(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    recommendation_id: "rec-1",
    type: "gap",
    title: "Posible laguna: Docker",
    description: "Docker es prerrequisito de Kubernetes pero está poco evidenciado",
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

describe("RecommendationsPanel", () => {
  it("no renderiza nada si no hay recomendaciones pendientes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ items: [], next_cursor: null })),
    );

    const { container } = render(<RecommendationsPanel />);

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("muestra las recomendaciones pendientes con su tipo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ items: [recommendation()], next_cursor: null })),
    );

    render(<RecommendationsPanel />);

    expect(await screen.findByText("Posible laguna: Docker")).toBeInTheDocument();
    expect(screen.getByText("Laguna")).toBeInTheDocument();
  });

  it("aceptar llama PATCH con status=accepted y quita la card de la lista", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (init?.method === "PATCH") {
        return Promise.resolve(jsonResponse(recommendation({ status: "accepted" })));
      }
      if (url.startsWith("/v1/recommendations")) {
        return Promise.resolve(jsonResponse({ items: [recommendation()], next_cursor: null }));
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<RecommendationsPanel />);
    const acceptButton = await screen.findByRole("button", { name: "Aceptar" });
    fireEvent.click(acceptButton);

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/v1/recommendations/rec-1",
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
    const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "PATCH")!;
    expect(JSON.parse(init!.body as string)).toEqual({ status: "accepted", reason: undefined });
    await waitFor(() =>
      expect(screen.queryByText("Posible laguna: Docker")).not.toBeInTheDocument(),
    );
  });

  it("descartar pide un motivo opcional y lo manda en el PATCH", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (init?.method === "PATCH") {
        return Promise.resolve(jsonResponse(recommendation({ status: "dismissed" })));
      }
      if (url.startsWith("/v1/recommendations")) {
        return Promise.resolve(jsonResponse({ items: [recommendation()], next_cursor: null }));
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<RecommendationsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Descartar" }));
    fireEvent.change(screen.getByLabelText("Motivo del descarte"), {
      target: { value: "ya lo sabía" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/v1/recommendations/rec-1",
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
    const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "PATCH")!;
    expect(JSON.parse(init!.body as string)).toEqual({
      status: "dismissed",
      reason: "ya lo sabía",
    });
  });
});
