import { describe, expect, it } from "vitest";
import {
  FOCUS_MARKS,
  FOCUS_TARGETS,
  clampFocusProgress,
  interpolateFocusMark,
  type FocusTarget,
} from "../src/lib/focus-mark";

const directedPairs = FOCUS_TARGETS.flatMap((from) =>
  FOCUS_TARGETS.filter((to) => to !== from).map((to) => [from, to] as const),
);

describe("focus mark geometry", () => {
  it("keeps a stable primitive budget for every lens", () => {
    for (const target of FOCUS_TARGETS) {
      expect(FOCUS_MARKS[target].edges).toHaveLength(34);
      expect(FOCUS_MARKS[target].nodes).toHaveLength(12);
      expect(FOCUS_MARKS[target].rings).toHaveLength(2);
    }
  });

  it.each(directedPairs)("reaches the exact %s → %s resting geometry", (from, to) => {
    const frame = interpolateFocusMark(FOCUS_MARKS[from], FOCUS_MARKS[to], 1);
    expect(frame).toEqual(FOCUS_MARKS[to]);
  });

  it.each(directedPairs)("produces a bounded intermediate frame for %s → %s", (from, to) => {
    const frame = interpolateFocusMark(FOCUS_MARKS[from], FOCUS_MARKS[to], 0.5);
    expect(frame).not.toEqual(FOCUS_MARKS[from]);
    expect(frame).not.toEqual(FOCUS_MARKS[to]);
    for (const edge of frame.edges) {
      expect(edge.opacity).toBeGreaterThanOrEqual(0);
      expect(edge.opacity).toBeLessThanOrEqual(1);
    }
    for (const node of frame.nodes) expect(node.opacity).toBeGreaterThanOrEqual(0);
  });

  it("preserves the approved static bridge silhouette", () => {
    const { edges, nodes } = FOCUS_MARKS.bridge;
    expect(edges.slice(0, 7)).toEqual([
      { x: 42, y: 160, toX: 136, toY: 76, opacity: 1, strokeWidth: 2 },
      { x: 136, y: 76, toX: 238, toY: 150, opacity: 1, strokeWidth: 2 },
      { x: 238, y: 150, toX: 342, toY: 54, opacity: 1, strokeWidth: 2 },
      { x: 342, y: 54, toX: 458, toY: 156, opacity: 1, strokeWidth: 2 },
      { x: 136, y: 76, toX: 202, toY: 32, opacity: 1, strokeWidth: 2 },
      { x: 238, y: 150, toX: 292, toY: 204, opacity: 1, strokeWidth: 2 },
      { x: 342, y: 54, toX: 390, toY: 112, opacity: 1, strokeWidth: 2 },
    ]);
    expect(nodes.slice(0, 8).map(({ x, y, r }) => ({ x, y, r }))).toEqual([
      { x: 42, y: 160, r: 9 }, { x: 136, y: 76, r: 13 }, { x: 238, y: 150, r: 10 }, { x: 342, y: 54, r: 14 },
      { x: 458, y: 156, r: 10 }, { x: 202, y: 32, r: 7 }, { x: 292, y: 204, r: 7 }, { x: 390, y: 112, r: 7 },
    ]);
  });

  it("clamps progress so rapid retargeting cannot overshoot", () => {
    const from = FOCUS_MARKS.bridge;
    const to = FOCUS_MARKS["ds-ml"];
    expect(interpolateFocusMark(from, to, -2)).toEqual(interpolateFocusMark(from, to, 0));
    expect(interpolateFocusMark(from, to, 2)).toEqual(interpolateFocusMark(from, to, 1));
    expect(clampFocusProgress(Number.NaN)).toBe(0);
    expect(clampFocusProgress(-0.02)).toBe(0);
    expect(clampFocusProgress(1.02)).toBe(1);
  });

  it("keeps every circle radius valid across the rapid directed switch sequence", () => {
    const sequence = ["ds-ml", "comp-bio", "bridge", "ds-ml", "comp-bio", "bridge"] as const;
    let current = FOCUS_MARKS.bridge;
    for (const target of sequence) {
      // A RAF timestamp can precede the transition start by a few milliseconds.
      for (const progress of [-0.02, 0, 0.5, 1, 1.02]) {
        const frame = interpolateFocusMark(current, FOCUS_MARKS[target], progress);
        for (const circle of [...frame.nodes, ...frame.rings]) {
          expect(Number.isFinite(circle.r)).toBe(true);
          expect(circle.r).toBeGreaterThanOrEqual(0);
        }
      }
      current = FOCUS_MARKS[target];
    }
    expect(current).toEqual(FOCUS_MARKS.bridge);
  });
});

// Keep the target type exercised in this test module so additions to the
// persisted lens contract remain explicit at compile time.
const _target: FocusTarget = "bridge";
void _target;
