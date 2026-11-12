import type { FocusTarget } from "./focus-mark";

export const REEL_TARGETS = ["bridge", "ds-ml", "comp-bio"] as const;
export type ReelTarget = FocusTarget;
export const isReelTarget = (value: unknown): value is ReelTarget =>
  REEL_TARGETS.some(target => target === value);
export const neighborTarget = (target: ReelTarget, direction: number): ReelTarget =>
  REEL_TARGETS[(REEL_TARGETS.indexOf(target) + direction + 3) % 3];

/** Six faces repeat three views so either direction wraps without a seam. */
export function reelPose(position: number, index: number) {
  const angle = (((index - position) * 60) % 360 + 540) % 360 - 180;
  const radians = angle * Math.PI / 180;
  const distance = Math.min(1, Math.abs(angle) / 60);
  return {
    angle, y: 110 * Math.sin(radians), z: 220 * (Math.cos(radians) - 1),
    scale: 1 - .38 * distance, opacity: Math.abs(angle) >= 90 ? 0 : 1 - .72 * distance,
  };
}

export function fitRatio(available: number, measured: number) {
  return available > 2 && measured > 0 ? Math.min(1, (available - 2) / measured) : 1;
}

export interface ReelClock {
  now(): number;
  request(callback: FrameRequestCallback): number;
  cancel(id: number): void;
}

/** DOM-independent motion: retarget from the actual frame, not the old endpoint. */
export class ReelMotion {
  position = 0;
  destination = 0;
  target: ReelTarget = "bridge";
  private frame = 0;
  private generation = 0;
  get running() { return this.frame !== 0; }
  constructor(private draw: (position: number, destination: number, target: ReelTarget) => void, private clock: ReelClock) {}
  private cancel() { this.clock.cancel(this.frame); this.frame = 0; this.generation += 1; }
  snap() {
    this.cancel(); this.position = this.destination;
    this.draw(this.position, this.destination, this.target);
  }
  select(target: ReelTarget, animate = true) {
    if (target === this.target) { if (!animate) this.snap(); return; }
    this.cancel();
    this.destination += neighborTarget(this.target, 1) === target ? 1 : -1;
    this.target = target;
    if (!animate) { this.snap(); return; }
    const start = this.position, destination = this.destination;
    const began = this.clock.now(), generation = this.generation;
    this.draw(this.position, destination, target);
    const tick = (now: number) => {
      if (generation !== this.generation) return;
      const elapsed = Number.isFinite(now - began) ? now - began : 0;
      const progress = Math.max(0, Math.min(1, elapsed / 560));
      this.position = start + (destination - start) * (1 - (1 - progress) ** 3);
      this.draw(this.position, destination, target);
      this.frame = progress < 1 ? this.clock.request(tick) : 0;
    };
    this.frame = this.clock.request(tick);
  }
}
