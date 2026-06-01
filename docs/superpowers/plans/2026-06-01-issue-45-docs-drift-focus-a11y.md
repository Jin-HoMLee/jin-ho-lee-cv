# Issue #45 — CLAUDE.md drift + global focus ring + keyboard-accessible chart — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two stale facts in `CLAUDE.md`, add a site-wide `:focus-visible` keyboard focus ring, and make the publication-chart pie slices keyboard-operable.

**Architecture:** Three independent, additive changes — one docs edit, one global CSS rule, one component (markup + client script) enhancement. No `content/*.yaml`, no Python renderer, no CI changes. Web changes are verified with a local Playwright run (system Chrome via the npx-cache module) against the production build, per repo convention (`reference_web_visual_verify`); not added to CI.

**Tech Stack:** Markdown, Tailwind v4 / plain CSS (`web/src/styles/global.css`), Astro component + vanilla DOM TypeScript (`web/src/components/PublicationsChart.astro`), Playwright (verification only).

**Spec:** `docs/superpowers/specs/2026-06-01-issue-45-docs-drift-focus-a11y-design.md`

---

## Files

- Modify: `CLAUDE.md` (intro phase count + "Files to read" list) — Task 1
- Modify: `web/src/styles/global.css` (add global `:focus-visible`) — Task 2
- Modify: `web/src/components/PublicationsChart.astro` (markup attrs + client script) — Task 3
- Verification scratch (not committed): `/tmp/verify_45_focus.mjs`, `/tmp/verify_45_chart.mjs`

**Shared verification harness** (used by Tasks 2 & 3 — build once, serve, drive with Playwright):

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
just web-build                                   # → web/dist/
# serve the static build in the background:
python3 -m http.server 4399 --directory web/dist >/tmp/http_45.log 2>&1 &
echo $! > /tmp/http_45.pid
# run a check (NODE_PATH points at the npx-cached playwright; channel:"chrome" = system Chrome):
NODE_PATH=/Users/jin-holee/.npm/_npx/e41f203b7505f1fb/node_modules node /tmp/verify_45_focus.mjs
# teardown when done:
kill "$(cat /tmp/http_45.pid)" 2>/dev/null || true
```

If `~/.npm/_npx/e41f203b7505f1fb` no longer exists, run `npx playwright --version` once to repopulate the cache and use the new `_npx/<hash>` path; or `npm i -g playwright`.

---

### Task 1: CLAUDE.md doc drift (Part A)

**Files:**
- Modify: `CLAUDE.md:15` (intro phase count)
- Modify: `CLAUDE.md:89-90` (insert six spec links)

- [ ] **Step 1: Fix the phase count (intro)**

Edit `CLAUDE.md` — replace exactly:
```
Eight phases (0–8), sequential. Each produces a usable artifact and gets its own brainstorm + plan + execution.
```
with:
```
Ten phases (0–9), sequential. Each produces a usable artifact and gets its own brainstorm + plan + execution.
```
(The `–` is an en-dash, U+2013 — keep it.)

- [ ] **Step 2: Add the Phase 6–9 spec links**

In `CLAUDE.md`, the "## Files to read before any phase" list currently ends its spec entries at the Phase 5 line. Insert the six lines below **immediately after** this existing line:
```
- `docs/superpowers/specs/2026-05-26-phase-5-polish-design.md` — Phase 5 design spec (custom domain, project pages, OG images, chart tooltips)
```
Inserted lines (before the `- `scripts/content_loader.py`…` line):
```
- `docs/superpowers/specs/2026-05-28-phase-6-seo-analytics-design.md` — Phase 6 design spec (sitemap, robots.txt, GSC verify, GoatCounter analytics)
- `docs/superpowers/specs/2026-05-29-phase-7-content-audit-design.md` — Phase 7 design spec (content audit — bring the CV up to date)
- `docs/superpowers/specs/2026-05-30-phase-8a-sharpen-positioning-design.md` — Phase 8a design spec (sharpen positioning — Bioinformatics · Data Science)
- `docs/superpowers/specs/2026-05-30-phase-8b-targeted-variants-design.md` — Phase 8b design spec (targeted CV variants — comp-bio · ds-ml from one source)
- `docs/superpowers/specs/2026-05-31-phase-8c-web-variants-design.md` — Phase 8c design spec (web target switcher — client-side variant positioning)
- `docs/superpowers/specs/2026-05-31-phase-9-web-redesign-design.md` — Phase 9 design spec (2026 dark-technical web overhaul)
```

- [ ] **Step 3: Verify**

Run:
```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
grep -c "Ten phases (0–9)" CLAUDE.md          # expect 1
grep -c "Eight phases" CLAUDE.md              # expect 0
for f in 2026-05-28-phase-6-seo-analytics 2026-05-29-phase-7-content-audit 2026-05-30-phase-8a-sharpen-positioning 2026-05-30-phase-8b-targeted-variants 2026-05-31-phase-8c-web-variants 2026-05-31-phase-9-web-redesign; do
  grep -q "$f" CLAUDE.md && test -f "docs/superpowers/specs/$f-design.md" && echo "OK $f" || echo "FAIL $f"
done
```
Expected: `1`, then `0`, then six `OK` lines (each link present **and** the file exists).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: #45 fix CLAUDE.md phase count + add Phase 6–9 spec links"
```

---

### Task 2: Global `:focus-visible` ring (Part B)

**Files:**
- Modify: `web/src/styles/global.css` (append after the `.eyebrow` block)
- Verify: `/tmp/verify_45_focus.mjs`

- [ ] **Step 1: Write the failing check**

Create `/tmp/verify_45_focus.mjs`:
```js
import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage();
await page.goto("http://localhost:4399/", { waitUntil: "networkidle" });

// Focus the first real <a> in the header nav and read its computed outline.
const handle = await page.evaluateHandle(() => {
  const el = document.querySelector("header a, header button, a[href], button");
  el.focus();
  return el;
});
const outline = await page.evaluate((el) => {
  const cs = getComputedStyle(el);
  return { width: cs.outlineWidth, style: cs.outlineStyle, color: cs.outlineColor };
}, handle);
console.log("focused element outline:", outline);
const ok = parseFloat(outline.width) >= 1.5 && outline.style === "solid";
console.log(ok ? "PASS focus ring present" : "FAIL no focus ring");
await browser.close();
process.exit(ok ? 0 : 1);
```

- [ ] **Step 2: Run it against the current build — verify it FAILS**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
just web-build
python3 -m http.server 4399 --directory web/dist >/tmp/http_45.log 2>&1 & echo $! > /tmp/http_45.pid
NODE_PATH=/Users/jin-holee/.npm/_npx/e41f203b7505f1fb/node_modules node /tmp/verify_45_focus.mjs
```
Expected: `FAIL no focus ring` (outline width `0px` / style `none`) — there is no global `:focus-visible` rule yet. (Leave the http server running for Step 4.)

- [ ] **Step 3: Add the global rule**

In `web/src/styles/global.css`, append after the `.eyebrow { … }` block:
```css
/* Site-wide keyboard focus ring. Mirrors CodeHero .cv-tab:focus-visible.
   :where() keeps specificity 0 so components can still override. */
:where(button, a, [role="button"]):focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

- [ ] **Step 4: Rebuild + verify it PASSES**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
just web-build
kill "$(cat /tmp/http_45.pid)" 2>/dev/null; python3 -m http.server 4399 --directory web/dist >/tmp/http_45.log 2>&1 & echo $! > /tmp/http_45.pid
NODE_PATH=/Users/jin-holee/.npm/_npx/e41f203b7505f1fb/node_modules node /tmp/verify_45_focus.mjs
```
Expected: `PASS focus ring present` (outline width `~2px`, style `solid`).
Note: `:focus-visible` may not paint under programmatic `.focus()` in every engine; if width reads `0` despite the rule being in the built CSS, re-run focusing via keyboard `await page.keyboard.press("Tab")` from `document.body` and re-read. The rule's presence in `web/dist/_astro/*.css` (grep `focus-visible`) is the authoritative check.

- [ ] **Step 5: Commit**

```bash
git add web/src/styles/global.css
git commit -m "feat(web): #45 site-wide :focus-visible keyboard focus ring"
```

---

### Task 3: Keyboard-operable pie slices (Part C)

**Files:**
- Modify: `web/src/components/PublicationsChart.astro` (frontmatter `computeArcs`, `<path>` markup, `<script>`)
- Verify: `/tmp/verify_45_chart.mjs`

- [ ] **Step 1: Write the failing check**

Create `/tmp/verify_45_chart.mjs`:
```js
import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage();
await page.goto("http://localhost:4399/", { waitUntil: "networkidle" });
await page.waitForTimeout(250);

const sel = "#publications svg path[data-label]";
const attrs = await page.$eval(sel, (p) => ({
  role: p.getAttribute("role"),
  tabindex: p.getAttribute("tabindex"),
  aria: p.getAttribute("aria-label"),
}));
console.log("first slice attrs:", attrs);

// focus → tooltip shows; Enter → toggles hidden
await page.$eval(sel, (p) => p.focus());
await page.waitForTimeout(100);
const shownOnFocus = await page.$eval("#publications .pub-tooltip", (t) => !t.classList.contains("hidden"));
await page.keyboard.press("Enter");
await page.waitForTimeout(100);
const hiddenAfterEnter = await page.$eval("#publications .pub-tooltip", (t) => t.classList.contains("hidden"));

const ok =
  attrs.role === "button" &&
  attrs.tabindex === "0" &&
  !!attrs.aria && /\d/.test(attrs.aria) &&
  shownOnFocus === true &&
  hiddenAfterEnter === true;
console.log({ shownOnFocus, hiddenAfterEnter });
console.log(ok ? "PASS chart keyboard-operable" : "FAIL chart not keyboard-operable");
await browser.close();
process.exit(ok ? 0 : 1);
```
(If `#publications` is not the section id, use the `<section>`/`<figure>` that wraps the chart — confirm with `grep -n "id=" web/src/components/PublicationsList.astro web/src/pages/index.astro`. The chart `<figure>` selector `figure.relative svg path[data-label]` also works and is id-independent — prefer it if unsure.)

- [ ] **Step 2: Run against current build — verify it FAILS**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
kill "$(cat /tmp/http_45.pid)" 2>/dev/null; python3 -m http.server 4399 --directory web/dist >/tmp/http_45.log 2>&1 & echo $! > /tmp/http_45.pid
NODE_PATH=/Users/jin-holee/.npm/_npx/e41f203b7505f1fb/node_modules node /tmp/verify_45_chart.mjs
```
Expected: `FAIL chart not keyboard-operable` (`role`/`tabindex`/`aria-label` are `null`; focus does nothing).

- [ ] **Step 3a: Single-source `pct` in `computeArcs`**

In `web/src/components/PublicationsChart.astro` frontmatter, change the `computeArcs` return object from:
```ts
    return { d, varName: colorVars[s.key], label: labels[s.key][lang], count: s.count };
```
to:
```ts
    const pct = ((s.count / total) * 100).toFixed(1);
    return { d, varName: colorVars[s.key], label: labels[s.key][lang], count: s.count, pct };
```

- [ ] **Step 3b: Add a11y attributes to each `<path>`**

Replace the `<path>` element in the markup:
```astro
      <path
        d={arc.d}
        style={`fill: var(${arc.varName})`}
        data-label={arc.label}
        data-count={arc.count}
        data-pct={((arc.count / total) * 100).toFixed(1)}
        class="cursor-pointer"
      />
```
with:
```astro
      <path
        d={arc.d}
        style={`fill: var(${arc.varName})`}
        data-label={arc.label}
        data-count={arc.count}
        data-pct={arc.pct}
        tabindex="0"
        role="button"
        aria-label={`${arc.label}: ${arc.count} (${arc.pct}%)`}
        class="cursor-pointer"
      />
```

- [ ] **Step 3c: Make `show()` position-source-agnostic + add keyboard/focus listeners**

In the `<script>`, replace the `show` definition:
```ts
    const show = (e: MouseEvent | TouchEvent, target: SVGPathElement) => {
      const label = target.dataset.label ?? "";
      const count = target.dataset.count ?? "";
      const pct = target.dataset.pct ?? "";
      tooltip.textContent = `${label}: ${count} (${pct}%)`;
      tooltip.classList.remove("hidden");
      const rect = fig.getBoundingClientRect();
      const point = "touches" in e ? e.touches[0] : e;
      tooltip.style.left = `${point.clientX - rect.left + 8}px`;
      tooltip.style.top = `${point.clientY - rect.top + 8}px`;
    };
```
with (widen the event type; position from the path's bbox when the event carries no pointer coords — i.e. focus/keydown):
```ts
    const show = (e: Event, target: SVGPathElement) => {
      const label = target.dataset.label ?? "";
      const count = target.dataset.count ?? "";
      const pct = target.dataset.pct ?? "";
      tooltip.textContent = `${label}: ${count} (${pct}%)`;
      tooltip.classList.remove("hidden");
      const rect = fig.getBoundingClientRect();
      const usePointer =
        e.type === "mouseenter" || e.type === "mousemove" || e.type === "touchstart";
      if (usePointer) {
        const pe = e as MouseEvent | TouchEvent;
        const point = "touches" in pe ? pe.touches[0] : pe;
        tooltip.style.left = `${point.clientX - rect.left + 8}px`;
        tooltip.style.top = `${point.clientY - rect.top + 8}px`;
      } else {
        const b = target.getBoundingClientRect();
        tooltip.style.left = `${b.left + b.width / 2 - rect.left}px`;
        tooltip.style.top = `${b.top + b.height / 2 - rect.top}px`;
      }
    };
```
Then, in the `paths.forEach((p) => { … })` block, after the existing `touchstart` listener, add:
```ts
      // Keyboard: focus surfaces the datum; Enter/Space toggles; blur hides.
      p.addEventListener("focus", (e) => show(e, p));
      p.addEventListener("blur", hide);
      p.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
          e.preventDefault();
          if (tooltip.classList.contains("hidden")) show(e, p);
          else hide();
        }
      });
```
(The existing mouse/touch listeners still call `show(e, p)` — unchanged, and `e.type` routes them through the pointer branch.)

- [ ] **Step 4: Rebuild + verify it PASSES**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
just web-build
kill "$(cat /tmp/http_45.pid)" 2>/dev/null; python3 -m http.server 4399 --directory web/dist >/tmp/http_45.log 2>&1 & echo $! > /tmp/http_45.pid
NODE_PATH=/Users/jin-holee/.npm/_npx/e41f203b7505f1fb/node_modules node /tmp/verify_45_chart.mjs
```
Expected: `PASS chart keyboard-operable` (`role=button`, `tabindex=0`, numeric `aria-label`; `shownOnFocus=true`, `hiddenAfterEnter=true`).

- [ ] **Step 5: Confirm the focus ring renders on a focused slice (SVG-outline contingency)**

```bash
NODE_PATH=/Users/jin-holee/.npm/_npx/e41f203b7505f1fb/node_modules node -e '
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch({ channel: "chrome", headless: true });
  const p = await b.newPage();
  await p.goto("http://localhost:4399/", { waitUntil: "networkidle" });
  const w = await p.$eval("figure.relative svg path[data-label]", (el) => { el.focus(); return getComputedStyle(el).outlineWidth; });
  console.log("slice outlineWidth:", w);
  await b.close();
})();
'
```
Expected: a non-zero width (e.g. `2px`). **If it reads `0px`**, the global `[role="button"]` rule did not paint on the SVG `<path>` in Chromium — add this scoped fallback inside the `<style>` of `PublicationsChart.astro` and rebuild:
```css
  svg path[role="button"]:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
```
(If `outline` still fails on SVG, use `stroke: var(--accent); stroke-width: 0.04;` instead.) Re-run this step until non-zero.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/PublicationsChart.astro
git commit -m "feat(web): #45 keyboard-operable publication chart slices"
```

---

### Task 4: Full regression gate + cleanup

**Files:** none (verification only)

- [ ] **Step 1: Green the suites**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
just validate && just test && just lint && just web-build
```
Expected: all pass (no Python was touched, but this is the standard pre-merge gate; `web-build` confirms TS/Astro compile).

- [ ] **Step 2: Tear down the http server**

```bash
kill "$(cat /tmp/http_45.pid)" 2>/dev/null || true
```

- [ ] **Step 3: Tick issue #45 checkboxes**

Verify each box in issue #45 (body has 4: phase-count, files-to-read, global `:focus-visible`, optional SVG a11y) is genuinely satisfied, then tick all four via `gh issue edit 45 --body-file <file>` (per `feedback_pr_test_plans`). The "(Optional)" SVG box is now in scope and done.

---

## Notes for the executor

- **No `content/*.yaml` edits** — renderer-isolation principle. This issue is docs + web-renderer only.
- **No CI changes** — Playwright stays a local verification tool, not a committed CI test (avoids new infra for a size-S issue).
- **Atomic commits** — three feature commits (Tasks 1–3), no Claude attribution trailers.
- **CLAUDE.md phase table** — unchanged. #45 is a maintenance item, not a phase; do **not** add a phasing-table row (consistent with #41/#43/#46). This plan's only CLAUDE.md edit is the drift fix that IS the task.
