export const FOCUS_TARGETS = ["bridge", "ds-ml", "comp-bio"] as const;
export type FocusTarget = (typeof FOCUS_TARGETS)[number];

export interface FocusPoint {
  x: number;
  y: number;
}

export interface FocusEdge extends FocusPoint {
  toX: number;
  toY: number;
  opacity: number;
  strokeWidth: number;
}

export interface FocusNode extends FocusPoint {
  r: number;
  opacity: number;
  fill: "var(--surface)" | "currentColor";
  stroke: "currentColor" | "none";
  strokeWidth: number;
}

export interface FocusRing extends FocusPoint {
  r: number;
  opacity: number;
  strokeWidth: number;
  dash: string;
}

export interface FocusMark {
  edges: FocusEdge[];
  nodes: FocusNode[];
  rings: FocusRing[];
}

const EDGE_COUNT = 34;
const NODE_COUNT = 12;
const RING_COUNT = 2;
const hiddenEdge = (): FocusEdge => ({ x: 0, y: 0, toX: 0, toY: 0, opacity: 0, strokeWidth: 0 });
const hiddenNode = (): FocusNode => ({ x: 0, y: 0, r: 0, opacity: 0, fill: "currentColor", stroke: "none", strokeWidth: 0 });
const hiddenRing = (): FocusRing => ({ x: 0, y: 0, r: 0, opacity: 0, strokeWidth: 0, dash: "" });
const pad = <T>(items: T[], count: number, makeHidden: () => T): T[] =>
  [...items, ...Array.from({ length: Math.max(0, count - items.length) }, makeHidden)];

const edge = (x: number, y: number, toX: number, toY: number, strokeWidth: number): FocusEdge => ({
  x, y, toX, toY, opacity: 1, strokeWidth,
});
const bridgeNode = (x: number, y: number, r: number): FocusNode => ({
  x, y, r, opacity: 1, fill: "var(--surface)", stroke: "currentColor", strokeWidth: 2,
});
const mlNode = (x: number, y: number, r: number): FocusNode => ({
  x, y, r, opacity: 1, fill: "currentColor", stroke: "none", strokeWidth: 0,
});

const bridgeEdges = [
  edge(42, 160, 136, 76, 2), edge(136, 76, 238, 150, 2), edge(238, 150, 342, 54, 2), edge(342, 54, 458, 156, 2),
  edge(136, 76, 202, 32, 2), edge(238, 150, 292, 204, 2), edge(342, 54, 390, 112, 2),
];
const bridgeNodes = [
  bridgeNode(42, 160, 9), bridgeNode(136, 76, 13), bridgeNode(238, 150, 10), bridgeNode(342, 54, 14),
  bridgeNode(458, 156, 10), bridgeNode(202, 32, 7), bridgeNode(292, 204, 7), bridgeNode(390, 112, 7),
];

const compEdges: FocusEdge[] = [];
const upper = [45, 60, 90, 140, 170, 185, 170, 140, 90, 60, 45, 60];
const lower = [185, 170, 140, 90, 60, 45, 60, 90, 140, 170, 185, 170];
const xs = [30, 70, 110, 150, 190, 230, 270, 310, 350, 390, 430, 470];
for (let i = 0; i < xs.length - 1; i += 1) {
  compEdges.push(edge(xs[i], upper[i], xs[i + 1], upper[i + 1], 2));
}
for (let i = 0; i < xs.length - 1; i += 1) {
  compEdges.push(edge(xs[i], lower[i], xs[i + 1], lower[i + 1], 2));
}
for (let i = 0; i < xs.length; i += 1) compEdges.push(edge(xs[i], upper[i], xs[i], lower[i], 2));

// The production mark's source viewBox is 160×58. The shared canvas is
// 500×230, while the panel viewport is 500×190; compensate for the different
// preserveAspectRatio fit so its settled screen geometry stays pixel-equivalent.
const ML_SCALE = 575 / 152;
const ML_X = -1000 / 19;
const ML_Y = 805 / 152;
const mlPoint = (x: number, y: number): FocusPoint => ({ x: x * ML_SCALE + ML_X, y: y * ML_SCALE + ML_Y });
const mlEdge = (x: number, y: number, toX: number, toY: number): FocusEdge => {
  const from = mlPoint(x, y);
  const to = mlPoint(toX, toY);
  return edge(from.x, from.y, to.x, to.y, 1.15);
};
const mlEdges = [
  mlEdge(18, 14, 58, 10), mlEdge(18, 14, 58, 23), mlEdge(18, 29, 58, 23), mlEdge(18, 29, 58, 35), mlEdge(18, 44, 58, 35), mlEdge(18, 44, 58, 48),
  mlEdge(58, 10, 103, 18), mlEdge(58, 23, 103, 18), mlEdge(58, 23, 103, 40), mlEdge(58, 35, 103, 18), mlEdge(58, 35, 103, 40), mlEdge(58, 48, 103, 40),
  mlEdge(103, 18, 139, 29), mlEdge(103, 40, 139, 29),
];
const mlNodesSource = [
  [18, 14, 2.4], [18, 29, 2.4], [18, 44, 2.4], [58, 10, 2.2], [58, 23, 2.2], [58, 35, 2.2], [58, 48, 2.2],
  [103, 18, 2.7], [103, 40, 2.7], [139, 29, 3.2],
] as const;
const mlNodes = mlNodesSource.map(([x, y, r]) => {
  const point = mlPoint(x, y);
  return mlNode(point.x, point.y, r * ML_SCALE);
});
const mlRings = [11, 17].map((r): FocusRing => {
  const point = mlPoint(139, 29);
  return { x: point.x, y: point.y, r: r * ML_SCALE, opacity: 1, strokeWidth: 1.15, dash: r === 17 ? "7.8125 10.9375" : "" };
});

export const FOCUS_MARKS: Record<FocusTarget, FocusMark> = {
  bridge: { edges: pad(bridgeEdges, EDGE_COUNT, hiddenEdge), nodes: pad(bridgeNodes, NODE_COUNT, hiddenNode), rings: pad([], RING_COUNT, hiddenRing) },
  "ds-ml": { edges: pad(mlEdges, EDGE_COUNT, hiddenEdge), nodes: pad(mlNodes, NODE_COUNT, hiddenNode), rings: mlRings },
  "comp-bio": { edges: pad(compEdges, EDGE_COUNT, hiddenEdge), nodes: pad([], NODE_COUNT, hiddenNode), rings: pad([], RING_COUNT, hiddenRing) },
};

export interface FocusFrame {
  edges: FocusEdge[];
  nodes: FocusNode[];
  rings: FocusRing[];
}

export function clampFocusProgress(progress: number): number {
  return Number.isFinite(progress) ? Math.max(0, Math.min(1, progress)) : 0;
}

export function interpolateFocusMark(from: FocusMark | FocusFrame, to: FocusMark, progress: number): FocusFrame {
  const t = clampFocusProgress(progress);
  if (t === 0 || t === 1) return t === 0 ? from : to;
  const mix = (a: number, b: number) => a + (b - a) * t;
  return {
    edges: to.edges.map((target, i) => {
      const source = from.edges[i];
      return { x: mix(source.x, target.x), y: mix(source.y, target.y), toX: mix(source.toX, target.toX), toY: mix(source.toY, target.toY), opacity: mix(source.opacity, target.opacity), strokeWidth: mix(source.strokeWidth, target.strokeWidth) };
    }),
    nodes: to.nodes.map((target, i) => {
      const source = from.nodes[i];
      return { ...target, x: mix(source.x, target.x), y: mix(source.y, target.y), r: mix(source.r, target.r), opacity: mix(source.opacity, target.opacity), strokeWidth: mix(source.strokeWidth, target.strokeWidth) };
    }),
    rings: to.rings.map((target, i) => {
      const source = from.rings[i];
      return { ...target, x: mix(source.x, target.x), y: mix(source.y, target.y), r: mix(source.r, target.r), opacity: mix(source.opacity, target.opacity), strokeWidth: mix(source.strokeWidth, target.strokeWidth) };
    }),
  };
}
