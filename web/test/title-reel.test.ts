import { describe, expect, it } from "vitest";
import { REEL_TARGETS, ReelMotion, fitRatio, neighborTarget, reelPose, type ReelClock } from "../src/lib/title-reel";

function setup() {
  let now = 0, id = 0;
  const frames = new Map<number, FrameRequestCallback>();
  const clock: ReelClock = { now: () => now, request: cb => { frames.set(++id, cb); return id; }, cancel: key => { frames.delete(key); } };
  const draws: number[] = [];
  const motion = new ReelMotion(position => draws.push(position), clock);
  const tick = (time: number) => { now = time; const pending = [...frames.values()]; frames.clear(); pending.forEach(cb => cb(time)); };
  return { motion, draws, tick, frames };
}

describe("approved transparent title reel", () => {
  it.each(REEL_TARGETS)("cycles reversibly from %s", target => {
    expect(neighborTarget(neighborTarget(target, 1), -1)).toBe(target);
    expect(neighborTarget(neighborTarget(neighborTarget(target, 1), 1), 1)).toBe(target);
  });
  it("recedes, tilts and shrinks one 60-degree step away from the front", () => {
    expect(reelPose(0, 0)).toEqual({ angle: 0, y: 0, z: 0, scale: 1, opacity: 1 });
    const next = reelPose(0, 1), previous = reelPose(0, 5);
    expect(next.angle).toBe(60); expect(previous.angle).toBe(-60);
    expect(next.y).toBeGreaterThan(90); expect(previous.y).toBeLessThan(-90);
    expect(next.z).toBeCloseTo(-110); expect(next.scale).toBeCloseTo(.62); expect(next.opacity).toBeCloseTo(.28);
    expect(reelPose(0, 3).opacity).toBe(0);
    expect(reelPose(6, 0)).toEqual(reelPose(0, 0));
  });
  it("animates 560ms and reverses from the actual in-flight position", () => {
    const { motion, draws, tick } = setup();
    motion.select("ds-ml"); tick(200);
    const midway = motion.position;
    expect(midway).toBeGreaterThan(0); expect(midway).toBeLessThan(1);
    motion.select("bridge"); expect(motion.position).toBe(midway);
    tick(400); expect(motion.position).toBeLessThan(midway);
    tick(760); expect(motion.position).toBe(0); expect(motion.running).toBe(false);
    expect(draws.every(Number.isFinite)).toBe(true);
  });
  it("ignores repeated selections and clamps early RAF timestamps", () => {
    const { motion, tick, frames } = setup();
    motion.select("bridge"); expect(frames.size).toBe(0);
    motion.select("ds-ml"); tick(-2); expect(motion.position).toBe(0);
    tick(560); expect(motion.position).toBe(1);
    motion.select("ds-ml"); expect(frames.size).toBe(0);
  });
  it("restores silently without frames and snaps when reduced motion becomes active", () => {
    const { motion, tick, frames } = setup();
    motion.select("comp-bio", false); expect(motion.position).toBe(-1); expect(frames.size).toBe(0);
    motion.select("bridge"); tick(100); motion.snap();
    expect(motion.position).toBe(0); expect(frames.size).toBe(0); expect(motion.running).toBe(false);
  });
  it("cancels stale callbacks during rapid cycles and finishes on the selected view", () => {
    const { motion, tick, frames } = setup();
    motion.select("ds-ml"); const stale = [...frames.values()][0];
    motion.select("comp-bio"); motion.select("bridge"); stale(1000);
    expect(motion.position).toBe(0); tick(560);
    expect(motion.destination).toBe(3); expect(motion.position).toBe(3); expect(motion.target).toBe("bridge");
  });
  it("fits longer localized wording without enlarging already-fitting titles", () => {
    expect(fitRatio(256, 200)).toBe(1);
    expect(fitRatio(256, 300)).toBeCloseTo(254 / 300);
    expect(fitRatio(0, 0)).toBe(1);
  });
});
