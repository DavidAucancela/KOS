import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GraphCanvas } from "../src/features/graph/GraphCanvas";
import type { GraphNode, GraphRelation } from "../src/features/graph/types";

function node(overrides: Partial<GraphNode> = {}): GraphNode {
  return {
    id: "node-1",
    node_type: "Technology",
    canonical_name: "docker",
    name: "Docker",
    aliases: [],
    confidence: 0.4,
    sources: ["doc-a"],
    extracted_by: "parser@v1",
    locked: false,
    created_at: null,
    updated_at: null,
    prune_candidate: false,
    ...overrides,
  };
}

function relation(overrides: Partial<GraphRelation> = {}): GraphRelation {
  return {
    id: "rel-1",
    relation_type: "USES",
    source_id: "node-1",
    target_id: "node-2",
    confidence: 0.7,
    sources: ["doc-a"],
    extracted_by: "parser@v1",
    extracted_at: null,
    rejected: false,
    prune_candidate: false,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe("GraphCanvas", () => {
  it("muestra un mensaje si no hay nodos", () => {
    render(<GraphCanvas nodes={[]} relations={[]} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText("Sin nodos para dibujar.")).toBeInTheDocument();
  });

  it("dibuja un nodo por cada elemento y una línea por cada relación inducida", () => {
    const nodes = [node(), node({ id: "node-2", canonical_name: "proyecto-kos" })];
    const { container } = render(
      <GraphCanvas nodes={nodes} relations={[relation()]} selectedId={null} onSelect={() => {}} />,
    );

    expect(screen.getByText("docker")).toBeInTheDocument();
    expect(screen.getByText("proyecto-kos")).toBeInTheDocument();
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    expect(container.querySelectorAll("line")).toHaveLength(1);
  });

  it("no dibuja relaciones hacia un nodo fuera del conjunto mostrado", () => {
    const nodes = [node()];
    const { container } = render(
      <GraphCanvas nodes={nodes} relations={[relation()]} selectedId={null} onSelect={() => {}} />,
    );

    expect(container.querySelectorAll("line")).toHaveLength(0);
  });

  it("clickear un nodo llama a onSelect con su id", () => {
    const onSelect = vi.fn();
    render(
      <GraphCanvas nodes={[node()]} relations={[]} selectedId={null} onSelect={onSelect} />,
    );

    fireEvent.click(screen.getByText("docker"));

    expect(onSelect).toHaveBeenCalledWith("node-1");
  });

  it("resalta el nodo seleccionado con un trazo distinto", () => {
    const nodes = [node(), node({ id: "node-2", canonical_name: "proyecto-kos" })];
    const { container } = render(
      <GraphCanvas nodes={nodes} relations={[]} selectedId="node-2" onSelect={() => {}} />,
    );

    const circles = Array.from(container.querySelectorAll("circle"));
    const selected = circles.find((circle) => circle.getAttribute("stroke-width") === "3");
    expect(selected).toBeDefined();
  });

  describe("zoom y pan", () => {
    beforeEach(() => {
      // jsdom no calcula layout real: sin esto, getBoundingClientRect() de la
      // svg devuelve todo en 0 y el código de zoom/pan (que divide por el
      // ancho/alto reales) se queda quieto a propósito (guardrail contra
      // división por cero) — 1:1 con WIDTH/HEIGHT simplifica las cuentas.
      vi.spyOn(SVGSVGElement.prototype, "getBoundingClientRect").mockReturnValue({
        left: 0,
        top: 0,
        width: 800,
        height: 520,
        right: 800,
        bottom: 520,
        x: 0,
        y: 0,
        toJSON: () => {},
      });
      // jsdom no implementa la Pointer Events API completa (setPointerCapture
      // no existe en sus elementos) — se lo tapa igual que getBoundingClientRect.
      Element.prototype.setPointerCapture = vi.fn();
    });

    function transformOf(container: HTMLElement): { x: number; y: number; k: number } {
      const raw = container.querySelector("svg > g")?.getAttribute("transform") ?? "";
      const match = /translate\(([-.\d]+), ([-.\d]+)\) scale\(([-.\d]+)\)/.exec(raw);
      if (!match) throw new Error(`transform inesperado: ${raw}`);
      return { x: Number(match[1]), y: Number(match[2]), k: Number(match[3]) };
    }

    it("la rueda del mouse cambia la escala", () => {
      const { container } = render(
        <GraphCanvas nodes={[node()]} relations={[]} selectedId={null} onSelect={() => {}} />,
      );
      const svg = container.querySelector("svg")!;

      expect(transformOf(container)).toEqual({ x: 0, y: 0, k: 1 });
      fireEvent.wheel(svg, { deltaY: -100, clientX: 400, clientY: 260 });

      const after = transformOf(container);
      expect(after.k).toBeCloseTo(1.1);
      // El punto bajo el cursor (400, 260 = el centro del viewBox) debe
      // quedar fijo mientras cambia el zoom, no desplazarse.
      expect(after.x).toBeCloseTo(-40);
      expect(after.y).toBeCloseTo(-26);
    });

    it("arrastrar el fondo desplaza el contenido (pan)", () => {
      const { container } = render(
        <GraphCanvas nodes={[node()]} relations={[]} selectedId={null} onSelect={() => {}} />,
      );
      const background = container.querySelector("rect")!;

      fireEvent.pointerDown(background, { clientX: 100, clientY: 100 });
      fireEvent.pointerMove(container.querySelector("svg")!, { clientX: 150, clientY: 130 });

      expect(transformOf(container)).toEqual({ x: 50, y: 30, k: 1 });
    });

    it("'Restablecer vista' vuelve la transformación a identidad", () => {
      const { container } = render(
        <GraphCanvas nodes={[node()]} relations={[]} selectedId={null} onSelect={() => {}} />,
      );
      const background = container.querySelector("rect")!;
      fireEvent.pointerDown(background, { clientX: 100, clientY: 100 });
      fireEvent.pointerMove(container.querySelector("svg")!, { clientX: 150, clientY: 130 });
      expect(transformOf(container)).not.toEqual({ x: 0, y: 0, k: 1 });

      fireEvent.click(screen.getByRole("button", { name: "Restablecer vista" }));

      expect(transformOf(container)).toEqual({ x: 0, y: 0, k: 1 });
    });
  });
});
