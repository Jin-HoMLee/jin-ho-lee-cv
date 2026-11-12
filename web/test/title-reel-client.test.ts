import { afterEach, describe, expect, it, vi } from "vitest";
import { mountTitleReels } from "../src/lib/title-reel-client";

// Isolated DOM/media doubles: these exercise wiring and announcements, not pixels
// or the user's OS preference. Real built-page geometry is checked separately.
class Element extends EventTarget {
  dataset: Record<string, string> = {};
  styles = new Map<string, string>();
  style = { opacity:"", transform:"", top:"", height:"", setProperty:(key:string,value:string) => this.styles.set(key,value), removeProperty:(key:string) => this.styles.delete(key) };
  classes = new Set<string>();
  classList = { contains:(name:string) => this.classes.has(name), add:(name:string) => this.classes.add(name), toggle:(name:string,force:boolean) => force ? this.classes.add(name) : this.classes.delete(name) };
  attrs = new Map<string,string>();
  selectors = new Map<string, Element>();
  lists = new Map<string, Element[]>();
  hidden = true; clientWidth = 508; offsetWidth = 200; writes = 0; private text = "";
  get textContent() { return this.text; }
  set textContent(value:string) { this.text = value; this.writes += 1; }
  querySelector(key:string) { return this.selectors.get(key); }
  querySelectorAll(key:string) { return this.lists.get(key) ?? []; }
  getBoundingClientRect() { return { top:0, bottom:255, left:0, right:544, width:544, height:255 }; }
  setAttribute(key:string,value:string) { this.attrs.set(key,value); }
  click() { this.dispatchEvent(new Event("click")); }
}
function setup(reduced = false, saved = "bridge") {
  vi.stubGlobal("ResizeObserver", class { observe() {} });
  const media = Object.assign(new EventTarget(), { matches:reduced });
  const frames = new Map<number, FrameRequestCallback>(); let id = 0;
  const win = Object.assign(new EventTarget(), { matchMedia:() => media, performance:{ now:() => 0 }, requestAnimationFrame:(cb:FrameRequestCallback) => { frames.set(++id,cb); return id; }, cancelAnimationFrame:(key:number) => frames.delete(key) });
  const root = new Element(), inputs = new Element(), status = new Element(), headline = new Element();
  root.dataset = { previewLabel:"Preview", previousLabel:"Previous view", nextLabel:"Next view" };
  for (const key of ["[data-reel-stage]", "[data-reel-before]", "[data-reel-after]"]) root.selectors.set(key,new Element());
  root.selectors.set("[data-reel-inputs]",inputs); root.selectors.set("[data-reel-status]",status); root.selectors.set("h1",headline);
  const faces = Array.from({ length:6 }, (_,index) => {
    const face = new Element(); face.dataset = { target:["bridge","ds-ml","comp-bio"][index % 3], name:["Default","DS · ML","Comp Bio"][index % 3] };
    face.lists.set(".title-line",Array.from({ length:2 }, () => { const line = new Element(); line.selectors.set("[data-title-word]",new Element()); return line; })); return face;
  });
  root.lists.set("[data-reel-face]",faces);
  const buttons = [-1,1,-1,1].map(direction => { const button = new Element(); button.dataset.reelStep = String(direction); return button; });
  inputs.lists.set("[data-reel-step]",buttons); inputs.selectors.set(".top",buttons[0]); inputs.selectors.set(".bottom",buttons[1]);
  let selected = saved;
  const lens = Object.fromEntries(["bridge","ds-ml","comp-bio"].map(target => {
    const button = new Element(); button.dataset.cvTarget = target;
    button.addEventListener("click",() => { selected = target; headline.textContent = target + " headline"; win.dispatchEvent(new CustomEvent("cv-target-change",{ detail:{ target, animate:true } })); }); return [target,button];
  }));
  const doc = { defaultView:win, fonts:{ ready:Promise.resolve(), addEventListener() {} }, createRange:() => ({ selectNodeContents() {}, getBoundingClientRect:() => root.getBoundingClientRect() }), querySelectorAll:() => [root], querySelector:(key:string) => key.includes('aria-pressed="true"') ? lens[selected] : lens[key.match(/data-cv-target="([^"]+)"/)?.[1] ?? ""] };
  mountTitleReels(doc as unknown as Document);
  return { root, inputs, status, frames, media, buttons, lens };
}
afterEach(() => vi.unstubAllGlobals());
describe("title reel integration", () => {
  it("restores the switcher's selected lens silently with reduced motion and no RAF", () => {
    const { root, frames, status, buttons } = setup(true,"comp-bio");
    expect(root.dataset.reelTarget).toBe("comp-bio"); expect(frames.size).toBe(0); expect(status.writes).toBe(0);
    buttons[3].click();
    expect(root.dataset.reelTarget).toBe("bridge"); expect(frames.size).toBe(0); expect(status.writes).toBe(1);
  });
  it("fits every unprojected title line after a font load, including longer locale text", async () => {
    const { root } = setup();
    const lines = root.querySelectorAll("[data-reel-face]").flatMap(face => face.querySelectorAll(".title-line"));
    for (const line of lines) {
      line.clientWidth = 256;
      line.querySelector("[data-title-word]")!.offsetWidth = 300;
    }
    await Promise.resolve(); // document.fonts.ready remeasures every face
    for (const line of lines) expect(Number(line.styles.get("--reel-fit"))).toBeCloseTo(254 / 300);
  });
  it("routes preview/arrows/keys through the lens and announces each changed selection once", () => {
    const { root, frames, status, buttons, lens, inputs, media } = setup();
    buttons[1].click(); expect(root.dataset.reelTarget).toBe("ds-ml"); expect(frames.size).toBe(1); expect(status.writes).toBe(1);
    lens["ds-ml"].click(); expect(status.writes).toBe(1);
    const key = Object.assign(new Event("keydown",{ cancelable:true }),{ key:"ArrowUp" }); inputs.dispatchEvent(key);
    expect(key.defaultPrevented).toBe(true); expect(root.dataset.reelTarget).toBe("bridge"); expect(status.writes).toBe(2);
    buttons[3].click(); expect(status.writes).toBe(3);
    media.matches = true; media.dispatchEvent(new Event("change"));
    expect(frames.size).toBe(0); expect(root.dataset.reelPosition).toBe(root.dataset.reelDestination); expect(status.writes).toBe(3);
  });
});
