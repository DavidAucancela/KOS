import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StatusPage } from "../src/features/status/StatusPage";
import type { HealthResponse, ServiceStatus } from "../src/features/status/types";

const SERVICE_NAMES = ["postgres", "neo4j", "redis", "minio", "ollama"];

function okService(): ServiceStatus {
  return { status: "ok", latency_ms: 12.3, detail: null };
}

function healthResponse(): HealthResponse {
  return {
    status: "ok",
    services: Object.fromEntries(SERVICE_NAMES.map((name) => [name, okService()])),
  };
}

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("StatusPage", () => {
  it("muestra los cinco servicios y el estado global operativo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(healthResponse())));

    render(<StatusPage />);

    for (const name of SERVICE_NAMES) {
      expect(await screen.findByText(name)).toBeInTheDocument();
    }
    expect(screen.getByText("Operativo")).toBeInTheDocument();
    expect(screen.getAllByText("ok")).toHaveLength(SERVICE_NAMES.length);
  });

  it("muestra el error y su detail cuando un servicio falla", async () => {
    const body = healthResponse();
    body.status = "degraded";
    body.services.neo4j = {
      status: "error",
      latency_ms: 3001.0,
      detail: "connection refused",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(body)));

    render(<StatusPage />);

    expect(await screen.findByText("Degradado")).toBeInTheDocument();
    expect(screen.getByText("connection refused")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("muestra 'API inaccesible' si el fetch falla", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));

    render(<StatusPage />);

    expect(await screen.findByText("API inaccesible")).toBeInTheDocument();
  });
});
