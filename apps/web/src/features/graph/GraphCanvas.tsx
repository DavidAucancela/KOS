import type { PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from "d3-force";
import type { SimulationNodeDatum } from "d3-force";

import { NODE_TYPE_COLORS, type GraphNode, type GraphRelation } from "./types";

// Visualización del grafo (doc 06 §2 `subgraph`, Sprint 10): layout de fuerzas
// calculado una vez por cambio de datos (d3-force solo para la física, el
// render lo controla React vía SVG) y arrastre manual simple después — no hay
// simulación corriendo en vivo, así que no compite con el usuario moviendo un
// nodo.
const WIDTH = 800;
const HEIGHT = 520;
const TICKS = 300;

interface SimNode extends SimulationNodeDatum {
  id: string;
}

interface Point {
  x: number;
  y: number;
}

export function GraphCanvas({
  nodes,
  relations,
  selectedId,
  onSelect,
}: {
  nodes: GraphNode[];
  relations: GraphRelation[];
  selectedId: string | null;
  onSelect: (nodeId: string) => void;
}) {
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const positionsRef = useRef(positions);
  positionsRef.current = positions;
  const svgRef = useRef<SVGSVGElement>(null);
  const draggingId = useRef<string | null>(null);

  const degree = useMemo(() => {
    const counts = new Map<string, number>();
    for (const rel of relations) {
      counts.set(rel.source_id, (counts.get(rel.source_id) ?? 0) + 1);
      counts.set(rel.target_id, (counts.get(rel.target_id) ?? 0) + 1);
    }
    return counts;
  }, [relations]);

  useEffect(() => {
    if (nodes.length === 0) {
      setPositions({});
      return;
    }
    // Conserva la posición si el nodo ya estaba (re-fetch tras una corrección):
    // evita que el layout entero salte cuando solo cambió un campo.
    const previous = positionsRef.current;
    const simNodes: SimNode[] = nodes.map((node) => ({ id: node.id, ...previous[node.id] }));
    const nodeIds = new Set(nodes.map((node) => node.id));
    const simLinks = relations
      .filter((rel) => nodeIds.has(rel.source_id) && nodeIds.has(rel.target_id))
      .map((rel) => ({ source: rel.source_id, target: rel.target_id }));

    const simulation = forceSimulation<SimNode>(simNodes)
      .force("charge", forceManyBody().strength(-260))
      .force(
        "link",
        forceLink<SimNode, { source: string; target: string }>(simLinks)
          .id((node) => node.id)
          .distance(100),
      )
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide(32))
      .stop();

    for (let i = 0; i < TICKS; i += 1) simulation.tick();

    const next: Record<string, Point> = {};
    for (const simNode of simNodes) {
      next[simNode.id] = { x: simNode.x ?? WIDTH / 2, y: simNode.y ?? HEIGHT / 2 };
    }
    setPositions(next);
  }, [nodes, relations]);

  function toSvgPoint(clientX: number, clientY: number): Point | null {
    const svg = svgRef.current;
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    return {
      x: ((clientX - rect.left) / rect.width) * WIDTH,
      y: ((clientY - rect.top) / rect.height) * HEIGHT,
    };
  }

  function handleNodePointerDown(nodeId: string) {
    return (event: ReactPointerEvent<SVGCircleElement>) => {
      draggingId.current = nodeId;
      event.currentTarget.setPointerCapture(event.pointerId);
    };
  }

  function handleSvgPointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    const nodeId = draggingId.current;
    if (!nodeId) return;
    const point = toSvgPoint(event.clientX, event.clientY);
    if (!point) return;
    setPositions((current) => ({ ...current, [nodeId]: point }));
  }

  function handleSvgPointerUp() {
    draggingId.current = null;
  }

  if (nodes.length === 0) {
    return (
      <div className="text-muted-foreground border-border flex h-[520px] w-full items-center justify-center rounded-lg border text-sm">
        Sin nodos para dibujar.
      </div>
    );
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="border-border bg-card h-[520px] w-full touch-none rounded-lg border"
      onPointerMove={handleSvgPointerMove}
      onPointerUp={handleSvgPointerUp}
      onPointerLeave={handleSvgPointerUp}
      role="img"
      aria-label="Visualización del grafo de conocimiento"
    >
      <g stroke="var(--border)" strokeWidth={1}>
        {relations.map((rel) => {
          const from = positions[rel.source_id];
          const to = positions[rel.target_id];
          if (!from || !to) return null;
          return <line key={rel.id} x1={from.x} y1={from.y} x2={to.x} y2={to.y} />;
        })}
      </g>
      <g>
        {nodes.map((node) => {
          const point = positions[node.id];
          if (!point) return null;
          const radius = 10 + Math.min(degree.get(node.id) ?? 0, 8) * 1.5;
          const isSelected = node.id === selectedId;
          return (
            <g
              key={node.id}
              transform={`translate(${point.x}, ${point.y})`}
              onClick={() => onSelect(node.id)}
              role="button"
              aria-label={node.canonical_name}
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onSelect(node.id);
              }}
              className="cursor-pointer"
            >
              <circle
                r={radius}
                fill={NODE_TYPE_COLORS[node.node_type]}
                stroke={
                  isSelected ? "var(--foreground)" : node.locked ? "var(--primary)" : "var(--border)"
                }
                strokeWidth={isSelected ? 3 : node.locked ? 2 : 1}
                onPointerDown={handleNodePointerDown(node.id)}
              />
              <text
                y={radius + 14}
                textAnchor="middle"
                fontSize={11}
                fill="var(--foreground)"
                className="pointer-events-none select-none"
              >
                {node.canonical_name}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
