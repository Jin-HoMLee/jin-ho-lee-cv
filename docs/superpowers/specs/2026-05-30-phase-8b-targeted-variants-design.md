# Design: Phase 8b — Targeted CV variants

**Date:** 2026-05-30
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Predecessor work:** Phase 8a — Sharpen positioning (merged 2026-05-30, PR #36, commit `c3862f5`)

## 1. Context — second of a three-part arc

8a defined *what a positioning is* and shipped the single canonical **bridge** positioning (Bioinformatics · Data Science) that reads credibly to both markets at once. 8b branches that one positioning into **per-target variants** so a single source can build a CV tuned for each market actually being pursued.

| Part | Theme | Surface | Status |
|---|---|---|---|
| 8a | Sharpen positioning | `content/` copy only | ✅ Done |
| **8b** | **Targeted CV variants (comp-bio vs ds-ml from one source)** | **schema + loader + offline renderers + CI** | **this spec** |
| 8c | Visual showcase refresh (hero, career-arc, **target switcher**) | web | future |

The **web target-switcher UI is 8c's job**, not 8b's. 8b makes the variants *exist and be buildable* (data model + PDF + plain-text + CI); 8c later wires an interactive switcher onto the website. 8b therefore touches **no `web/` file** and leaves the Astro site rendering the bridge variant.

## 2. Problem

After 8a there is exactly one positioning. It is deliberately a "bridge" — equally weighted — which is the right canonical default but is nobody's *first choice*:

- A computational-biology hiring manager wants the genomics depth, wet-lab grounding, reproducible pipelines, and publication record leading — not "production ML on GCP" sharing the headline.
- A data-science / ML hiring manager wants production ML, cloud migration, and BigQueryML leading — with genomics as a rigorous research foundation, not the headline.

Today there is no way to produce either without hand-editing `content/`, which defeats the single-source principle. There is also latent, unused structure begging to be used: every project already carries a `category` tag (`life-science` ×5: L1–L5, `data-science` ×3: D1–D3, `consulting` ×2: C1–C2), but `content/selected_projects.yaml` is a hardcoded target-blind list `[L5, L1, L2]` and no renderer reads `category`.

## 3. Goal

From the single source, `just`-build a CV positioned for a chosen target:

- **Day-one deliverable:** `just build --target comp-bio` → `dist/cv-en-comp-bio.pdf`, a real targeted PDF you can send to a computational-biology employer; likewise `--target ds-ml`, both languages.
- A new **`target` axis** (`bridge` | `comp-bio` | `ds-ml`) sits orthogonal to the existing `lang` axis, resolved once in the content layer so **every renderer keeps consuming flat resolved scalars exactly as 8a left it** — zero per-renderer variant logic.
- **`bridge` is the strict canonical fallback.** Variants are *partial* overrides; any field a variant does not override inherits bridge. A variant can be a one-line headline swap.
- Bridge output keeps its **current unsuffixed filenames** (`cv-en.pdf`, `cv-de.pdf`) so nothing 8a/CI shipped is renamed or broken.
- EN/DE parity maintained for every variant.

## 4. What varies — positioning-only

A target variant overrides **only** these four positioning surfaces:

| Surface | Source field | Bridge (today) |
|---|---|---|
| Headline | `personal.yaml → headline` | `Bioinformatics · Data Science` |
| Tagline | `profile.{en,de}.yaml → tagline` | `Data scientist with cancer-genomics roots …` |
| Lead paragraph | `profile.{en,de}.yaml → paragraphs[0]` | `Data scientist with deep roots in cancer genomics. …` |
| Featured-project order | `selected_projects.yaml` | `[L5, L1, L2]` |

**Shared across all targets** (never varies in 8b): profile **paragraph 2** (the industry-proof paragraph), every **experience** bullet, **skills**, **education**, **publications**. This is the deliberate boundary from the brainstorm — *positioning*, not *content curation*. Suppressing whole experience entries (e.g. hiding consulting work from the comp-bio build) is explicitly out of scope and a separable later concern.

## 5. Encoding — one consistent `base + variants` shape

The base field stays the bridge value (unchanged from 8a). Per-target overrides live in a sibling **`variants:`** map keyed by target id. Decisive property: variant keys (`comp-bio`, `ds-ml`) are **not** 2-letter lowercase codes, so the langstring resolver ([langstring.py:10-16](../../../scripts/langstring.py)) treats them as ordinary nested data and never mistakes them for a `{en,de}` langmap — the existing `{en,de}` resolution stays byte-identical and [langstring.py](../../../scripts/langstring.py) is **untouched**.

### 5.1 `personal.yaml`

```yaml
headline:                       # bridge default (unchanged)
  en: "Bioinformatics · Data Science"
  de: "Bioinformatik · Data Science"
variants:
  comp-bio:
    headline: { en: "Computational Biology · Cancer Genomics", de: "Computational Biology · Krebsgenomik" }
  ds-ml:
    headline: { en: "Data Science · Machine Learning", de: "Data Science · Machine Learning" }
```

### 5.2 `profile.{en,de}.yaml`

```yaml
tagline: "Data scientist with cancer-genomics roots — …"   # bridge default (unchanged)
paragraphs:                                                 # bridge default (unchanged)
  - "Data scientist with deep roots in cancer genomics. …"  # paragraphs[0] — lead
  - "Now applying that rigor in industry: …"                # paragraphs[1] — SHARED, never varies
variants:
  comp-bio:
    tagline: "Bioinformatician with a decade in cancer genomics — …"
    lead_paragraph: "Bioinformatician specializing in cancer genomics. …"
  ds-ml:
    tagline: "Data scientist shipping production ML on GCP — …"
    lead_paragraph: "Production-focused data scientist. …"
```

`lead_paragraph` replaces `paragraphs[0]` only; `paragraphs[1]` is inherited unchanged. Overriding a single field (not the whole `paragraphs` array) keeps the shared industry-proof paragraph defined in exactly one place per language.

### 5.3 `selected_projects.yaml`

Changes from a flat list to a target-keyed map of ordered lists. `bridge` is mandatory; target keys optional (fall back to `bridge`).

```yaml
bridge:   [L5, L1, L2]      # current order, preserved
comp-bio: [L1, L2, L5]      # neoantigen, HLA pipeline, reproducible splice workflow
ds-ml:    [C1, D1, D2]      # KYC/BigQueryML, real-time ASL ML, badminton AI  (illustrative)
```

## 6. Resolution — load-time, one path

`load_content` ([content_loader.py:49](../../../scripts/content_loader.py)) gains a keyword-only **`target`** parameter (default `"bridge"`, mirroring the existing `lang`) plus a **target-override pass** that runs on the freshly-loaded YAML before the tree is returned. `{en,de}` langmap resolution stays downstream in the renderers exactly as today — `load_content` still returns `headline` as a raw `{en,de}` map; the override pass only swaps *which* map/string is the base:

1. For any object carrying a `variants` map: if `variants[target]` exists, shallow-merge its keys over the base object; then **delete the `variants` key entirely** so it never reaches renderers, the schema-consuming code, or langstring resolution. (A `headline` override is itself an `{en,de}` map and replaces the base map wholesale, still raw for downstream resolution.)
2. For `profile`: if the chosen variant supplies `lead_paragraph`, set `paragraphs[0]` to it and drop the `lead_paragraph` key.
3. For `selected_projects`: select `map[target]`, falling back to `map["bridge"]`.
4. `target="bridge"` performs no overrides (the bridge values are already the base) but still strips `variants` keys.
5. Unknown `target` → raise (fail fast).

Because overrides resolve to the same flat scalars 8a produced, **all six render points and every renderer downstream stay unchanged** — they keep reading `headline`, `tagline`, `paragraphs`, and the project list with no knowledge a target axis exists.

## 7. Which renderers vary

| Renderer | Varies? | Change |
|---|---|---|
| **PDF** ([pdf/build.py](../../../pdf/build.py)) | ✅ | Add `--target` (choices `bridge`/`comp-bio`/`ds-ml`, default `bridge`); thread into `load_content(target=…)`. Typst templates **untouched**. Output `dist/cv-{lang}-{target}.pdf`; bridge → `dist/cv-{lang}.pdf` (unsuffixed). |
| **Plain text** ([render_text.py](../../../scripts/render_text.py)) | ✅ | Add `--target` (it already has `--lang`); same naming rule → `dist/cv-{lang}-{target}.txt`, bridge unsuffixed. |
| **JSON Resume** ([render_jsonresume.py](../../../scripts/render_jsonresume.py)) | ❌ | Stays canonical **bridge**. It is a machine/tooling contract; variant-splitting breaks JSON Resume tool assumptions. No `--target`. |
| **JSON-LD** ([render_jsonld.py](../../../scripts/render_jsonld.py)) | ❌ | Stays canonical **bridge**. One authoritative schema.org `Person`; splitting fragments search identity. `description = paragraphs[0]` continues to pin the bridge lead. |
| **Web** ([render_web_data.py](../../../scripts/render_web_data.py) + `web/`) | ❌ | **Untouched in 8b.** Site renders bridge. The interactive target switcher is **8c**. |

## 8. Schema & validation

**`schema/cv.schema.json`** (8a deliberately froze it; 8b reopens it minimally):

- Add an optional `variants` object to `personal` and to `profile`, keyed by a **target enum** `["comp-bio", "ds-ml"]` (`bridge` is the base, never a variant key — catches typos). `personal.variants.<target>` → optional `{ headline: LangString }`. `profile.variants.<target>` → optional `{ tagline?: string, lead_paragraph?: string }`.
- `selected_projects` becomes an object whose keys are `bridge` + the target enum, each an array of project-id strings; `bridge` required.

**`scripts/validate.py`** rules:

- Bridge base always present (already enforced: `headline` required on `personal`, `paragraphs` required on `profile`, `bridge` now required on `selected_projects`).
- **Target enum:** only `comp-bio` / `ds-ml` may appear as variant keys anywhere.
- **EN/DE variant parity:** if a target appears in `profile.en.yaml`'s `variants`, it must appear in `profile.de.yaml`'s with the same overridden keys, and vice-versa. A `headline` variant must carry both `en` and `de` (bridge headline has both).
- **Cross-references:** every project id in **every** `selected_projects` target list must resolve to a `content/projects/<id>.{en,de}.yaml` file (extends the existing cross-ref check, which today only walks the flat list).

## 9. Build tooling & CI

**`justfile`:** keep `build` / `build-de` as bridge (back-compat). Add a parameterized recipe (e.g. `build-target target lang="en"`) and a convenience `build-targets` that emits all six PDFs. Mirror for text if useful.

**`.github/workflows/ci.yml`:** the PDF build/release matrix expands from `lang:[en,de]` (2 jobs) to `lang × target` (6 jobs). Release attaches all six PDFs:

```text
cv-en.pdf  cv-de.pdf                 (bridge, unsuffixed — existing links unchanged)
cv-en-comp-bio.pdf  cv-de-comp-bio.pdf
cv-en-ds-ml.pdf     cv-de-ds-ml.pdf
```

Machine-format artifacts (JSON Resume, JSON-LD, plain text) stay **target-agnostic / bridge** in CI. The Pages deploy and the sitemap smoke-check ([ci.yml](../../../.github/workflows/ci.yml) — currently 22 URLs) are **unchanged**, because the web layer is untouched.

## 10. The variant copy (illustrative — finalized during execution)

Like 8a, the actual copy is a content deliverable refined during implementation (and a good place for the owner's eye). Constraints: **factual only — no invented metrics**, every number already in `content/`; EN/DE parity. Starting proposals:

- **comp-bio** — lead with genomics depth, wet-lab grounding, reproducible pipelines, publications; demote cloud/BigQueryML to the shared ¶2.
- **ds-ml** — lead with production ML on GCP, the 1,000+-process cloud migration, BigQueryML for AFC/KYC, coaching; frame cancer genomics as the rigorous research foundation.

Exact strings are set in the implementation plan / during execution, not frozen here.

## 11. Non-goals

- **No content curation.** Experience bullets, skills, education, publications, and ¶2 are shared across all targets. No per-target suppression of experience entries.
- **No web changes.** No `web/` file, no `render_web_data.py` change, no switcher — all 8c.
- **No variant machine formats.** JSON Resume and JSON-LD stay single canonical bridge.
- **No invented facts or metrics.**
- **No new targets** beyond `comp-bio` / `ds-ml` (plus the `bridge` base).
- **No langstring.py changes** — variant keys are not langmaps by construction.

## 12. Definition of done

1. `just validate` green (schema extended, all variant + cross-ref rules enforced).
2. `just test` green, including a new `tests/test_variants.py`:
   - bridge resolution is byte-identical to pre-8b (regression guard);
   - `comp-bio` / `ds-ml` override headline + tagline + `paragraphs[0]`, and **inherit** `paragraphs[1]`, experience, skills, education;
   - partial-variant fallback (a field not overridden returns the bridge value);
   - `selected_projects` returns the per-target order, falling back to bridge;
   - unknown target raises;
   - `test_positioning.py` still pins the bridge positioning.
3. `just lint` green.
4. `just build --target comp-bio` and `--target ds-ml`, both langs → six PDFs; bridge PDFs keep names `cv-en.pdf` / `cv-de.pdf`; variant PDFs show the target headline, tagline, re-led ¶1, and reordered projects; ¶2 + experience identical across all three.
5. `just build-text --target …` mirrors the PDF variants.
6. `just build-resume` / `just build-jsonld` unchanged (bridge).
7. CI matrix produces and the release attaches all six PDFs; Pages/sitemap unchanged.
8. EN/DE parity confirmed for every variant on every varying surface.

(Generated files under `dist/` and `web/src/data/` remain gitignored — 8b commits source YAML + Python + schema + tests + CI/justfile only, no build artifacts.)

## 13. Open details

- **Headline glyph:** keep 8a's `·` (U+00B7) separator in variant headlines for consistency.
- **`ds-ml` selected-projects:** confirm the ML-leading order during execution (C1/D1/D2 vs another mix) — depends on which projects best signal production ML.
- **`build-targets` ergonomics:** whether CI calls a single fan-out recipe or the matrix invokes `build --target` per cell (cosmetic; decide in the plan).

## 14. Commits / branch

Per repo convention (atomic commits; per-phase branch; `--no-ff` PR merge): branch `phase-8b-targeted-variants`, created via `gh issue develop` against a tracking issue so branch↔issue link. Anticipated atomic commit sequence (each lands green):

1. `feat(loader): add target axis with bridge fallback` — `content_loader.py` target-override pass + `tests/test_variants.py` core resolution/fallback (TDD: tests first).
2. `feat(schema): allow positioning variants + target-keyed selected_projects` — `cv.schema.json` + `validate.py` rules + validation tests.
3. `content: add comp-bio and ds-ml positioning variants` — `personal.yaml`, `profile.{en,de}.yaml`, `selected_projects.yaml` (EN/DE parity) + content assertions.
4. `feat(render): --target flag for PDF and plain-text builds` — `build.py`, `render_text.py`, `justfile` + filename-convention test.
5. `ci: build and release the target × lang PDF matrix` — `ci.yml`.
6. `docs: mark Phase 8b row in CLAUDE.md phasing table` — final task per repo convention.

A final verification pass (`just validate && just test && just lint` plus local `build`/`build-de`/variant builds) confirms every offline renderer carries the right copy; it commits nothing.
