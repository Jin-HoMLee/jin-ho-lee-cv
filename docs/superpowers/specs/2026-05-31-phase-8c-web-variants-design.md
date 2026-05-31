# Design: Phase 8c — Web Variants (client-side target switcher)

**Date:** 2026-05-31  
**Owner:** Jin-Ho Lee  
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)  
**Predecessor work:** Phase 8b — Targeted CV variants (merged 2026-05-30, PR #38, commit `b9f6895`)

## 1. Context — third of a three-part arc

8a defined positioning; 8b made variants exist at the data layer (backend); 8c wires the interactive experience on the website.

| Part | Theme | Surface | Status |
|---|---|---|---|
| 8a | Sharpen positioning | `content/` copy only | ✅ Done |
| 8b | Targeted CV variants (comp-bio vs ds-ml from one source) | schema + loader + offline renderers + CI | ✅ Done |
| **8c** | **Visual showcase refresh: client-side target switcher** | **web + render_web_data.py + Pages CI** | **this spec** |

8c keeps the site rendering bridge (remains SEO-canonical, sitemap-canonical, schema.org-canonical), but adds a **client-side hydrated island** — the TargetSwitcher component — that lets visitors instantly switch between variants *without a page reload*. Users see the exact same page, but positioned for their audience.

## 2. Problem

Phase 8b shipped the variants but left them invisible on the web:
- The Astro site renders the bridge variant only
- A computational-biology visitor sees "Data Science · Machine Learning" as the headline and the DS project list
- There is no way for them to see the same CV re-positioned for their market without manually requesting a different PDF

The variants exist (buildable as PDFs, in plain-text output), but the website does not expose them. This defeats the UX goal: *show one person, three angles, chooseable*.

## 3. Goal

From the bridge website, enable a visitor to **instantly switch between comp-bio and ds-ml variants** (and back to bridge) without reloading the page. All variant switching happens in the browser; no server request except for the variants metadata JSON (lazy-loaded on first switch).

- **Day-one deliverable:** A visible, intuitive target-switcher UI component that updates the CV in-place.
- The **bridge variant remains canonical** for SEO (sitemap, OG meta, schema.org `Person` all point to bridge).
- Variant preference is **optionally persisted** to `localStorage` so repeat visitors see their chosen target on return.
- **Zero impact on PDFs, JSON Resume, JSON-LD, or plain-text.** Those renderers continue to consume the `--target` flag directly.
- **Sitemap stays at 22 URLs** (unchanged); only the in-memory display varies.

## 4. Data shape — Approach 2: Separate variants metadata

The existing `render_web_data.py` outputs two files per language:

| File | Contains | Usage |
|---|---|---|
| `web/src/data/content.{en,de}.json` | Full bridge tree, resolved | Static Astro build; page renders at build-time |
| **`web/src/data/content.{en,de}.variants.json`** | **Overrides only** | **Loaded by TargetSwitcher on first switch** |

**Shape of `content.en.variants.json`:**
```json
{
  "comp-bio": {
    "headline": "Computational Biology · Cancer Genomics",
    "tagline": "Bioinformatician with a decade in cancer genomics …",
    "lead_paragraph": "Specializing in cancer genomics, I have spent a decade …",
    "selected_projects": ["L1", "L2", "L5"]
  },
  "ds-ml": {
    "headline": "Data Science · Machine Learning",
    "tagline": "Production-focused data scientist shipping ML on GCP …",
    "lead_paragraph": "I specialize in building and deploying machine-learning …",
    "selected_projects": ["C1", "D1", "D2"]
  }
}
```

Each target object contains **only the fields that vary** from bridge:
- `headline`
- `tagline`
- `lead_paragraph` (replaces the first element of `paragraphs` array)
- `selected_projects` (array of project IDs in desired order)

The variant JSON does **not** include bridge values. Merging is additive: bridge + variant overrides = display data.

### 4.1 Why this shape

- **Bridge stays lean:** No bloat in the main `content.json`; users with no interest in variants never fetch the variants file.
- **Clear audit trail:** By storing only overrides, it is immediately obvious *what* varies per target.
- **Lazy loading:** The variants file is fetched only on first target switch, not on every page load.
- **Language-scoped:** Each language has its own variants file (parallel to bridge structure), ensuring EN/DE parity is enforced by schema + validation.

## 5. Implementation — Three components

### 5.1 Python: expand `render_web_data.py`

**File:** `scripts/render_web_data.py`

**Today's behavior (unchanged for bridge):**
```python
for lang in LANGS:
    tree = load_content(content_dir, private_path=None, lang=lang)  # target="bridge" by default
    resolved = resolve_langstrings(tree, lang=lang)
    ...write web/src/data/content.{lang}.json...
```

**New: render variants metadata**
```python
for lang in LANGS:
    # Load each variant
    variants_dict = {}
    for target in ["comp-bio", "ds-ml"]:
        variant_tree = load_content(content_dir, private_path=None, lang=lang, target=target)
        variant_resolved = resolve_langstrings(variant_tree, lang=lang)
        
        # Bridge for comparison
        bridge_tree = load_content(content_dir, private_path=None, lang=lang, target="bridge")
        bridge_resolved = resolve_langstrings(bridge_tree, lang=lang)
        
        # Extract only changed fields
        overrides = _extract_overrides(bridge_resolved, variant_resolved)
        variants_dict[target] = overrides
    
    # Write variants metadata
    out_path = OUTPUT_DIR / f"content.{lang}.variants.json"
    out_path.write_text(
        json.dumps(variants_dict, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path}")
```

**Helper: `_extract_overrides(bridge, variant) -> dict`**
```python
def _extract_overrides(bridge: dict, variant: dict) -> dict:
    """Return only the fields that differ between bridge and variant."""
    overrides = {}
    for key in ["headline", "tagline", "lead_paragraph", "selected_projects"]:
        if bridge.get(key) != variant.get(key):
            overrides[key] = variant[key]
    return overrides
```

**Contract:** The function must be fast and must never include bridge values in the output. All assertions should be in validation (see section 8).

### 5.2 TypeScript: TargetSwitcher hydrated island

**File:** `web/src/components/TargetSwitcher.tsx` (new)

A **hydrated Astro component** (client-side React/Preact/Svelte, TBD by existing web stack choice).

**Pseudo-code (React example):**
```typescript
import { useEffect, useState, useRef } from "react";

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

  // On mount, check localStorage for saved preference
  useEffect(() => {
    const saved = localStorage.getItem("cvTargetPreference");
    if (saved && ["bridge", "comp-bio", "ds-ml"].includes(saved)) {
      setCurrentTarget(saved);
      applyVariant(saved);
    }
  }, []);

  // Lazy-load variants JSON on first switch away from bridge
  const ensureVariantsLoaded = async (): Promise<VariantsMap> => {
    if (variantsRef.current) return variantsRef.current;
    const resp = await fetch(`/data/content.${lang}.variants.json`);
    if (!resp.ok) throw new Error("Failed to load variants");
    variantsRef.current = await resp.json();
    return variantsRef.current;
  };

  // Apply variant overrides to global store
  const applyVariant = async (target: string) => {
    if (target === "bridge") {
      // Reset to bridge (already rendered at build time, no action needed)
      store.reset();
    } else {
      const variants = await ensureVariantsLoaded();
      const overrides = variants[target];
      if (!overrides) throw new Error(`Unknown target: ${target}`);
      store.applyOverrides(overrides);
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

**Key behaviors:**
- Defaults to bridge (zero-overhead on first visit)
- Loads variants JSON lazily (only if user clicks a variant button)
- Caches loaded variants in memory (no re-fetch on toggle)
- Persists choice to `localStorage` under key `cvTargetPreference`
- On return visit, auto-applies saved preference (but does not block page render)

**Placement:** Top of the CV card (above headline) or in a dedicated bar — UX TBD in the web styling phase. Should be visible but not intrusive.

**Store integration:** Assumes the Astro site uses a global data store (likely Nanostores or Svelte stores). The `store.applyOverrides()` method merges variant overrides into the current data tree and triggers reactivity. If no store exists, this may need scaffolding.

### 5.3 Astro layout: Wire the island

**File:** `web/src/layouts/BaseLayout.astro` (or relevant page template)

Insert the TargetSwitcher component as a **client:load island** (loads and hydrates on page load):

```astro
---
import TargetSwitcher from "../components/TargetSwitcher.tsx";
const lang = Astro.props.lang || "en";
---

<html lang={lang}>
  <head>...</head>
  <body>
    <main>
      <TargetSwitcher client:load lang={lang} />
      <!-- Rest of CV content -->
    </main>
  </body>
</html>
```

**Why `client:load`:** The switcher must be ready immediately (users may click before the page fully loads). Alternatives (`client:idle`, `client:visible`) would delay the first interaction.

## 6. Rendering & store logic (existing patterns)

The site already consumes `content.en.json` and `content.de.json`. The **store** (whatever reactive pattern Astro uses) likely reads these and updates the DOM.

**No changes to existing rendering code.** The TargetSwitcher simply calls `store.applyOverrides(overrides)`, which shallow-merges variant fields into the store. All downstream components read from the store; they stay agnostic to whether data is bridge or variant.

**Example store method (pseudo-code):**
```typescript
export const contentStore = atom({
  personal: { ... },
  profile: { ... },
  // ...
});

export function applyOverrides(overrides: Record<string, any>) {
  contentStore.set(prev => ({
    ...prev,
    ...overrides,
    // If lead_paragraph is in overrides, also update paragraphs[0]
    profile: prev.profile 
      ? { 
          ...prev.profile, 
          ...(overrides.lead_paragraph ? { paragraphs: [overrides.lead_paragraph, ...prev.profile.paragraphs.slice(1)] } : {})
        }
      : prev.profile,
  }));
}
```

## 7. CI/Pages workflow — minimal changes

**File:** `.github/workflows/pages.yml`

The existing "Render web JSON" step already calls `python -m scripts.render_web_data`. The expanded script now produces both `content.{en,de}.json` and `content.{en,de}.variants.json`. **No workflow change needed** — the script's invocation stays identical.

**New smoke-test (in pages.yml "Smoke-check build outputs"):**
```bash
# Verify variants JSON files exist and are valid
test -f web/dist/data/content.en.variants.json
test -f web/dist/data/content.de.variants.json
jq empty web/dist/data/content.en.variants.json || (echo "Invalid EN variants JSON" && exit 1)
jq empty web/dist/data/content.de.variants.json || (echo "Invalid DE variants JSON" && exit 1)
```

**Sitemap and SEO:** Unchanged. Sitemap still lists 22 URLs (bridge only); OG images, robots.txt, schema.org `Person` all remain bridge. Variant switching is **in-memory display only**, not a navigational or indexable change.

**Release artifacts:** Unchanged. CI releases the 6 PDFs (with `--target` variants) + machine formats (bridge). The web deploy is separate and the variants JSON is part of the built site (in `web/dist/data/`).

## 8. Schema & validation

**`schema/cv.schema.json`:** No changes. Variants are already defined in 8b; this phase only consumes them.

**`scripts/validate.py`:** No changes. Validation already enforces variant structure and EN/DE parity.

**New validation in `render_web_data.py`:** Add runtime checks:
- Each target in variants JSON must be one of the known targets (`comp-bio`, `ds-ml`)
- EN and DE variants must have identical keys (if `comp-bio.headline` exists in EN, it must exist in DE)
- `selected_projects` arrays must contain only valid project IDs
- Override values must **differ** from bridge (catch accidental no-ops)

**New test:** `tests/test_render_web_data_variants.py`
```python
def test_variants_json_valid():
    """Verify content.{en,de}.variants.json are valid JSON."""
    ...

def test_variants_en_de_parity():
    """Verify EN and DE variant keys match."""
    en_variants = json.load(open("web/src/data/content.en.variants.json"))
    de_variants = json.load(open("web/src/data/content.de.variants.json"))
    assert en_variants.keys() == de_variants.keys()
    for target in en_variants:
        assert en_variants[target].keys() == de_variants[target].keys()

def test_variants_differ_from_bridge():
    """Verify variant values actually differ from bridge."""
    bridge_en = json.load(open("web/src/data/content.en.json"))
    variants_en = json.load(open("web/src/data/content.en.variants.json"))
    for target, overrides in variants_en.items():
        for key, value in overrides.items():
            assert value != bridge_en.get(key), \
                f"{target}.{key} == bridge.{key}; override should differ"

def test_variants_projects_valid():
    """Verify project IDs in selected_projects are resolvable."""
    for lang in ["en", "de"]:
        variants = json.load(open(f"web/src/data/content.{lang}.variants.json"))
        for target, overrides in variants.items():
            if "selected_projects" in overrides:
                for proj_id in overrides["selected_projects"]:
                    assert (Path("content/projects") / f"{proj_id}.{lang}.yaml").exists(), \
                        f"Project {proj_id} not found"
```

## 9. Non-goals

- **Sitemap variants:** Do not add variant URLs to the sitemap. Bridge is the canonical URL.
- **SEO per-variant:** The site is indexable only at bridge. Variants are a user preference display, not separate pages.
- **PDF switcher:** PDFs are built with `--target`; no interactive component in the PDF itself.
- **Server-side rendering per-variant:** No pre-built variant sites. All switching is client-side.
- **Persistent variant storage beyond localStorage:** Do not add a server-side "remember my preference" feature in 8c. localStorage suffices.

## 10. Success criteria

- ✅ User can click "Comp Bio" and see headline + tagline + lead paragraph + project list update in-place.
- ✅ Switching back to bridge or to DS/ML works instantly (no network latency on second click).
- ✅ Preference persists across page reloads (localStorage).
- ✅ Variants JSON files exist, are valid, and contain only override keys.
- ✅ EN and DE variants have matching keys.
- ✅ Sitemap still has 22 URLs (unchanged).
- ✅ OG images, schema.org, robots.txt all remain bridge (unchanged).
- ✅ Tests pass; no existing tests break.

## 11. Dependencies & sequencing

**Blocks on:**
- 8b must be complete (variants data layer + `load_content(target=…)` exists)
- Web store/reactivity pattern must be clarified (how does TargetSwitcher signal updates?)

**Unblocks:**
- None in the immediate roadmap. 8c is the final scheduled phase of the codified-CV project.

## 12. Open questions for execution

1. **Store implementation:** What reactivity library does the Astro site use (Nanostores, Svelte, plain Signals, etc.)? The TargetSwitcher needs to know how to trigger updates.
2. **Component framework:** Which component framework is the site built in (React, Preact, Svelte)? The TypeScript pseudocode above assumes React.
3. **UI placement & styling:** Where should the TargetSwitcher appear visually? A buttons bar at the top, a toggle in the header, a card sidebar?
4. **localStorage behavior:** Should the preference auto-apply on page load (seamless return visit) or require the user to click again (explicit choice)?
5. **Fallback for JS-disabled visitors:** Should there be a server-side content variant (graceful degradation)? Or is JS required for the feature?

---

**Next step:** Execute phase 8c using subagent-driven development (see `docs/superpowers/plans/` template). Answer the open questions during the planning phase, then implement component-by-component with code-quality checkpoints.
