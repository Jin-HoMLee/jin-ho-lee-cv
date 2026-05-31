# Plan: Phase 8c — Web Variants (client-side target switcher)

**Date:** 2026-05-31  
**Owner:** Jin-Ho Lee  
**Design spec:** [`2026-05-31-phase-8c-web-variants-design.md`](../specs/2026-05-31-phase-8c-web-variants-design.md)

## Overview

Implement a client-side target switcher on the Astro website so visitors can instantly switch between comp-bio, ds-ml, and bridge variants. The switcher loads variant metadata JSON on-demand and applies overrides to the in-memory data tree. Bridge remains the canonical, SEO-default variant.

**Sequencing:** 8 tasks, cleanest dependency flow: Python layer → validation → TypeScript component → Astro wiring → CI updates → testing.

---

## Task 1: Add `_extract_overrides()` helper to `render_web_data.py`

**Goal:** Build the foundation function that extracts only the changed fields between bridge and variant trees.

**Files touched:** `scripts/render_web_data.py`

**Effort:** ~30 mins

**Acceptance criteria:**
- Function exists and is tested
- Given two identical dicts, returns `{}`
- Given dicts differing in `headline` and `tagline`, returns both overrides
- Ignores unchanged fields
- Never includes bridge values in output

**Steps:**
1. Open `scripts/render_web_data.py`
2. Add function:
   ```python
   def _extract_overrides(bridge: dict, variant: dict) -> dict:
       """Return only the fields that differ between bridge and variant.
       
       Args:
           bridge: Fully-resolved bridge tree (all keys present)
           variant: Fully-resolved variant tree (all keys present)
       
       Returns:
           Dict with only the keys that differ; empty dict if identical.
       """
       OVERRIDE_KEYS = {"headline", "tagline", "lead_paragraph", "selected_projects"}
       overrides = {}
       for key in OVERRIDE_KEYS:
           bridge_val = bridge.get(key)
           variant_val = variant.get(key)
           if bridge_val != variant_val:
               overrides[key] = variant_val
       return overrides
   ```
3. Verify the function is reachable and callable in the module

---

## Task 2: Implement `render_web_data()` to output variants JSON

**Goal:** Expand the render function to write both `content.{lang}.json` (bridge, existing) and `content.{lang}.variants.json` (overrides, new).

**Files touched:** `scripts/render_web_data.py`

**Effort:** ~1 hour

**Blockers:** Requires Task 1 (the `_extract_overrides` helper)

**Acceptance criteria:**
- After running `python -m scripts.render_web_data`, both JSON files exist
- `content.en.variants.json` and `content.de.variants.json` are valid JSON
- Each contains exactly two keys: `"comp-bio"` and `"ds-ml"`
- No bridge values leak into variant dicts
- `selected_projects` array in variants is a list of strings

**Steps:**
1. In `render_web_data()`, after the existing bridge loop, add a new loop:
   ```python
   # NEW: Render variants metadata
   for lang in LANGS:
       variants_dict = {}
       bridge_tree = load_content(content_dir, private_path=None, lang=lang, target="bridge")
       bridge_resolved = resolve_langstrings(bridge_tree, lang=lang)
       
       for target in ["comp-bio", "ds-ml"]:
           variant_tree = load_content(content_dir, private_path=None, lang=lang, target=target)
           variant_resolved = resolve_langstrings(variant_tree, lang=lang)
           overrides = _extract_overrides(bridge_resolved, variant_resolved)
           variants_dict[target] = overrides
       
       jsonable_variants = _to_jsonable(variants_dict)
       out_path = OUTPUT_DIR / f"content.{lang}.variants.json"
       out_path.write_text(
           json.dumps(jsonable_variants, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
           encoding="utf-8",
       )
       print(f"wrote {out_path}")
   ```
2. Test manually: `uv run python -m scripts.render_web_data` and inspect `web/src/data/content.en.variants.json`
3. Verify the JSON structure matches the design (no bridge values, only override keys)

---

## Task 3: Add validation tests for variants JSON

**Goal:** Write pytest suite to validate variants JSON correctness (EN/DE parity, no bridge leaks, project IDs valid).

**Files touched:** `tests/test_render_web_data_variants.py` (new)

**Effort:** ~1 hour

**Blockers:** Requires Task 2 (variants JSON must exist)

**Acceptance criteria:**
- New test file exists and has at least 4 test functions
- All tests pass after running `pytest tests/test_render_web_data_variants.py`
- Tests enforce: EN/DE key parity, no bridge values, valid project IDs, override values differ

**Steps:**
1. Create `tests/test_render_web_data_variants.py`:
   ```python
   import json
   from pathlib import Path
   
   VARIANTS_EN = Path(__file__).parent.parent / "web" / "src" / "data" / "content.en.variants.json"
   VARIANTS_DE = Path(__file__).parent.parent / "web" / "src" / "data" / "content.de.variants.json"
   BRIDGE_EN = Path(__file__).parent.parent / "web" / "src" / "data" / "content.en.json"
   BRIDGE_DE = Path(__file__).parent.parent / "web" / "src" / "data" / "content.de.json"
   
   def test_variants_json_valid():
       """Verify both variants JSON files exist and parse."""
       assert VARIANTS_EN.exists(), f"Missing {VARIANTS_EN}"
       assert VARIANTS_DE.exists(), f"Missing {VARIANTS_DE}"
       en = json.loads(VARIANTS_EN.read_text())
       de = json.loads(VARIANTS_DE.read_text())
       assert isinstance(en, dict)
       assert isinstance(de, dict)
   
   def test_variants_en_de_parity():
       """EN and DE must have identical target keys."""
       en = json.loads(VARIANTS_EN.read_text())
       de = json.loads(VARIANTS_DE.read_text())
       assert en.keys() == de.keys(), f"Key mismatch: EN={en.keys()}, DE={de.keys()}"
       for target in en:
           en_override_keys = set(en[target].keys())
           de_override_keys = set(de[target].keys())
           assert en_override_keys == de_override_keys, \
               f"{target}: EN keys={en_override_keys}, DE keys={de_override_keys}"
   
   def test_variants_no_bridge_leaks():
       """Variant values must actually differ from bridge."""
       bridge = json.loads(BRIDGE_EN.read_text())
       variants = json.loads(VARIANTS_EN.read_text())
       for target, overrides in variants.items():
           for key, value in overrides.items():
               bridge_val = bridge.get(key)
               assert value != bridge_val, \
                   f"{target}.{key} == bridge.{key} (should differ); override invalid"
   
   def test_variants_projects_exist():
       """All project IDs in selected_projects must be resolvable."""
       projects_dir = Path(__file__).parent.parent / "content" / "projects"
       for lang, variants_file in [("en", VARIANTS_EN), ("de", VARIANTS_DE)]:
           variants = json.loads(variants_file.read_text())
           for target, overrides in variants.items():
               if "selected_projects" in overrides:
                   for proj_id in overrides["selected_projects"]:
                       proj_path = projects_dir / f"{proj_id}.{lang}.yaml"
                       assert proj_path.exists(), \
                           f"Project {proj_id}.{lang}.yaml not found (referenced in {target})"
   ```
2. Run `pytest tests/test_render_web_data_variants.py -v`
3. All tests pass; if not, debug Task 2 output

---

## Task 4: Update smoke-check in `.github/workflows/pages.yml`

**Goal:** Add validation that variants JSON files are built correctly in CI.

**Files touched:** `.github/workflows/pages.yml`

**Effort:** ~20 mins

**Blockers:** Requires Task 2 (must exist for CI to check)

**Acceptance criteria:**
- Smoke-check section in pages.yml includes checks for variants JSON
- On CI, the step passes after build
- Detects missing or invalid JSON files

**Steps:**
1. In `.github/workflows/pages.yml`, find the "Smoke-check build outputs" section
2. Add before the final `grep -q` line:
   ```bash
   # Verify variants JSON files exist and are valid
   test -f web/dist/data/content.en.variants.json || (echo "Missing EN variants JSON" && exit 1)
   test -f web/dist/data/content.de.variants.json || (echo "Missing DE variants JSON" && exit 1)
   jq empty web/dist/data/content.en.variants.json || (echo "Invalid EN variants JSON" && exit 1)
   jq empty web/dist/data/content.de.variants.json || (echo "Invalid DE variants JSON" && exit 1)
   ```
3. Test locally with `pnpm --dir web build` (or manually inspect `web/dist/data/`)

---

## Task 5: Clarify store/reactivity pattern on the Astro site

**Goal:** Determine how the website implements state management and reactivity (Nanostores, Svelte, Signals, plain React, etc.) so the TargetSwitcher component can integrate correctly.

**Files touched:** None (research only)

**Effort:** ~15 mins

**Blockers:** None (can start immediately)

**Acceptance criteria:**
- Document (comment or memo) which store/framework is used
- Identify the method/API for updating the content store from a component
- Clarify how reactive updates trigger component re-renders

**Steps:**
1. Inspect `web/src/components/` to see existing component patterns
2. Check `web/astro.config.mjs` for integration hints (React? Svelte? Preact?)
3. Look at `web/package.json` for store dependencies (nanostores? zustand?)
4. Find an example component that updates/reads shared state
5. Document the pattern (add a comment to the top of TargetSwitcher.tsx pseudocode)

---

## Task 6: Create `TargetSwitcher.tsx` component (with store integration)

**Goal:** Implement the hydrated Astro island that manages target switching, lazy-loads variants JSON, and updates the store.

**Files touched:** `web/src/components/TargetSwitcher.tsx` (new)

**Effort:** ~1.5–2 hours

**Blockers:** Requires Task 5 (must know store API before implementing)

**Acceptance criteria:**
- Component file exists and compiles (no TypeScript errors)
- Three buttons rendered: Default, Comp Bio, DS/ML
- Clicking a button fetches `content.{lang}.variants.json` on first switch
- Variant JSON is cached in memory (no re-fetch on toggle)
- Preference stored/restored from localStorage under key `cvTargetPreference`
- Component accepts `lang` prop
- Component hydrates with `client:load` directive

**Steps:**
1. Create `web/src/components/TargetSwitcher.tsx`:
   ```typescript
   // Pseudocode structure (fill in actual store API from Task 5)
   import { useEffect, useState, useRef } from "react"; // or Preact/Svelte equivalent
   
   interface Variant {
     headline?: string;
     tagline?: string;
     lead_paragraph?: string;
     selected_projects?: string[];
   }
   
   interface VariantsMap {
     [target: string]: Variant;
   }
   
   export default function TargetSwitcher({ lang }: { lang: "en" | "de" }) {
     const [currentTarget, setCurrentTarget] = useState<string>("bridge");
     const variantsRef = useRef<VariantsMap | null>(null);
   
     useEffect(() => {
       const saved = localStorage.getItem("cvTargetPreference");
       if (saved && ["bridge", "comp-bio", "ds-ml"].includes(saved)) {
         setCurrentTarget(saved);
         applyVariant(saved);
       }
     }, []);
   
     const ensureVariantsLoaded = async (): Promise<VariantsMap> => {
       if (variantsRef.current) return variantsRef.current;
       const resp = await fetch(`/data/content.${lang}.variants.json`);
       if (!resp.ok) throw new Error("Failed to load variants");
       variantsRef.current = await resp.json();
       return variantsRef.current;
     };
   
     const applyVariant = async (target: string) => {
       if (target === "bridge") {
         // Reset to bridge — use store.reset() or store.setData(originalBridge)
         // Fill in based on actual store API from Task 5
       } else {
         const variants = await ensureVariantsLoaded();
         const overrides = variants[target];
         if (!overrides) throw new Error(`Unknown target: ${target}`);
         // Apply overrides via store — fill in actual API
       }
       setCurrentTarget(target);
       localStorage.setItem("cvTargetPreference", target);
     };
   
     const targets = [
       { id: "bridge", label: "Default" },
       { id: "comp-bio", label: "Comp Bio" },
       { id: "ds-ml", label: "DS / ML" },
     ];
   
     return (
       <div className="target-switcher">
         <p className="label">View as:</p>
         <div className="button-group">
           {targets.map(({ id, label }) => (
             <button
               key={id}
               onClick={() => applyVariant(id)}
               className={`target-btn ${currentTarget === id ? "active" : ""}`}
               aria-pressed={currentTarget === id}
             >
               {label}
             </button>
           ))}
         </div>
       </div>
     );
   }
   ```
2. Compile and verify no TypeScript errors: `pnpm --dir web run typecheck`
3. Commit component (even if not wired yet)

---

## Task 7: Wire TargetSwitcher island into the layout

**Goal:** Place the TargetSwitcher component as a hydrated island in the Astro base layout so it appears on every page.

**Files touched:** `web/src/layouts/BaseLayout.astro` (or equivalent main template)

**Effort:** ~20 mins

**Blockers:** Requires Task 6 (component must exist)

**Acceptance criteria:**
- TargetSwitcher renders visibly on the homepage
- Component is hydrated (interactive, not static HTML)
- Buttons are clickable
- No hydration errors in browser console
- Component has access to the `lang` prop from the route

**Steps:**
1. Identify the main Astro layout file (likely `web/src/layouts/BaseLayout.astro` or similar)
2. Import the component at the top:
   ```astro
   import TargetSwitcher from "../components/TargetSwitcher.tsx";
   ```
3. Add the component instance with `client:load`:
   ```astro
   <div class="cv-header">
     <TargetSwitcher client:load lang={lang} />
     <!-- Rest of CV header -->
   </div>
   ```
   (Exact placement TBD by visual design; "top of CV" is the principle)
4. Build site locally: `pnpm --dir web build`
5. Inspect `web/dist/index.html` to verify the component is included
6. Optionally run `pnpm --dir web dev` and manually test buttons in browser

---

## Task 8: End-to-end testing & CI green-light

**Goal:** Verify the full feature works: variants JSON exists, component loads, switcher responds, localStorage persists, sitemap is unchanged.

**Files touched:** None (testing only)

**Effort:** ~1–1.5 hours

**Blockers:** Requires all prior tasks (1–7)

**Acceptance criteria:**
- `pytest tests/test_render_web_data_variants.py -v` passes
- `pnpm --dir web build` succeeds with no errors
- Smoke-check in CI passes (includes variants JSON checks)
- Browser E2E test (manual or Playwright) demonstrates: click Comp Bio → headline updates → switch to DS/ML → updates again → bridge button → resets
- localStorage persists choice (refresh page, preference is remembered)
- Sitemap still has exactly 22 URLs
- All existing tests pass (no regressions)

**Steps:**
1. Run all tests:
   ```bash
   uv run pytest tests/ -v
   pytest tests/test_render_web_data_variants.py -v
   ```
2. Build web locally:
   ```bash
   pnpm --dir web build
   ```
3. Inspect artifacts:
   ```bash
   test -f web/dist/data/content.en.json
   test -f web/dist/data/content.en.variants.json
   jq . web/dist/data/content.en.variants.json | head -20  # visual inspection
   ```
4. Manual browser test (or add Playwright E2E):
   - Open `http://localhost:3000` (dev mode) or inspect built output
   - Click "Comp Bio" button
   - Verify headline changes in the DOM
   - Open DevTools → Application → localStorage → check `cvTargetPreference`
   - Refresh page; verify headline stays comp-bio (preference persisted)
   - Click "Default" → should revert
5. If all manual checks pass, commit and push

---

## Commit checklist

Before merging to main (or opening PR):

- [ ] All pytest tests pass (`pytest tests/ -v`)
- [ ] TypeScript compiles (`pnpm --dir web run typecheck`)
- [ ] Web builds (`pnpm --dir web build`)
- [ ] Smoke-check in CI passes (can test locally by running `web/dist/` checks manually)
- [ ] Variants JSON files exist and are valid
- [ ] Component renders and is interactive (browser E2E or manual test)
- [ ] Existing tests still pass (no regressions)
- [ ] Commit message follows conventions (atomic, plain message, no Claude trailers)

---

## Final phase-completion task

Update `CLAUDE.md`:
- Mark Phase 8c **✅ Done** in the Phasing table
- Add row: `| 8c | Visual showcase refresh (target switcher) | web + render_web_data.py + Pages CI | ✅ Done (merged YYYY-MM-DD, commit `<sha>`) |`
- Note any new conventions or learnings (e.g., "Astro islands with TypeScript state management")

---

## Summary

**Phase 8c** closes the loop: variants are data-driven, PDFs are targeted, and the website is now an interactive showcase of all three angles. The bridge variant remains canonical for SEO; switching is instant and local. No new infrastructure, no server-side rendering, no sitemap explosion.

**Total estimated effort:** 6–7 hours (serial tasks 1–8). Can be split across days; tasks 5–7 are parallelizable with task 3–4 if you want to pipeline work.

**Success outcome:** User lands on CV, sees bridge positioning by default, clicks "Comp Bio" and sees cancer-genomics headline + lead + projects. localStorage remembers the choice. All PDF/text/JSON variants still build via CI. Sitemap and SEO untouched.
