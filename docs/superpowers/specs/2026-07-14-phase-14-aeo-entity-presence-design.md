# Phase 14 - AEO entity presence: design

**Date:** 2026-07-14
**Issue:** [#113](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/113)
**Grounding:** `docs/research/2026-07-01-aeo-answer-engine-optimization.md` (the adversarially-verified AEO deep-research report)

## Why

Answer engines resolve "Jin-Ho Lee" to *this* person only if external anchors disambiguate the entity, and they read static HTML only (no JS execution).
The verified levers, in leverage order: entity disambiguation (`sameAs` + a Wikidata item), crawler-readable static facts, FAQ/QAPage schema, answer-shaped content.
`llms.txt` is proven inert and stays out of scope.

## Scope

All four deferred items from #113, ordered by leverage-per-effort:

1. Wikidata item (+ Google Scholar in `sameAs`)
2. Static-HTML-facts audit with a permanent CI guard
3. `FAQPage` JSON-LD + visible FAQ section, seeded from the 12b twin question log
4. Answer-shaped profile block (index page only)

## Locked decisions

- **Two-tier visibility boundary.** `content/` is the public tier and must be crawler-readable in static HTML.
The `master-cv/` overlay is deliberately twin-exclusive: crawlers not seeing it is a feature (a reason to talk to the twin), not a gap.
FAQ answers are grounded in `content/` facts only, never the overlay.
- **FAQ placement:** compact collapsible section on the index page(s); no separate `/faq` route.
- **FAQ freshness:** curated `content/faq.yaml`, refreshed manually when the insights dashboard surfaces new question themes; no automation.
- **FAQ languages:** full LangString `{en, de}`, both required at authoring time (the site has a complete `/de/` mirror).
- **Wikidata depth:** professional core only - name, occupation, field of work, ORCID, GitHub, website, country.
No birth date, employer, or alma mater (privacy-deliberate).
Created by Jin-Ho's own account, referenced from published sources, mindful of notability policy.
- **Google Scholar:** profile exists - `https://scholar.google.com/citations?user=QPyM-WoAAAAJ` (canonical form, no `hl` param).
- **Answer block:** profile/index page only; per-project answer blocks deferred until twin-log questions show demand.

## Design

### Content and data model

**`content/faq.yaml` (new).**
A `faqs:` list; each entry is `{ id, question: {en, de}, answer: {en, de} }`.
`id` is a unique kebab-case slug; list order is display order.
A header comment states the grounding rule: every answer must be derivable from `content/` facts only (editorial rule, enforced at review time).
Initial seeding during execution: pull real question themes from the 12b insights dashboard and curate roughly 5-8 entries.

**`schema/faq.schema.json` (new).**
Wired into `scripts/validate.py` like the existing per-file schemas.
Enforces unique ids, kebab-case id shape, and required non-empty `en` + `de` on both question and answer, so `just validate` fails loudly on a half-translated FAQ.

**Answer block (new profile field).**
One authored 40-60 word `answer_block` string in each of `profile.en.yaml` / `profile.de.yaml`.
Bridge-level only, deliberately not per-variant: the target switcher is client-side JS, so crawlers only ever see bridge content.
Schema: optional field (the CV schema gains the key; absence renders nothing).

**`content/personal.yaml` links.**
Add `googlescholar` immediately; add `wikidata` only after the item exists (a runbook step, never a placeholder).
Consumer effects, all verified:

- JSON-LD `_same_as` picks up new keys automatically (the point of the exercise).
- JSON Resume `_network_for` gains mappings: `googlescholar` → "Google Scholar", `wikidata` → "Wikidata".
- The plain-text renderer appends all links to its header line; accepted - the `.txt` CV is machine-facing and entity anchors help there.
- The PDF header picks explicit keys only, so the PDF stays untouched.
- All golden snapshots regenerate intentionally (`just snapshots-update`, diff eyeballed).

### Rendering and data flow

**Pipeline.**
`content_loader.load_content` gains `"faq": _load_yaml(content_dir / "faq.yaml")` (required file, like every other content file - no graceful-absence machinery).
FAQ text flows through the existing LangString resolution into `content.{en,de}.json` via `render_web_data.py`; no new render script.
The answer block rides along as a profile field.

**`FaqSection.astro` (new component).**
Rendered on `index.astro` and `de/index.astro`, after the main content grid (FAQ is crawler bait, not the human pitch).
Each entry is a `<details><summary>` pair: full Q&A text present in static HTML regardless of open/closed state.
Section heading from a new `labels.yaml` key (`{en, de}`).

**FAQPage JSON-LD.**
The same component emits a `<script type="application/ld+json">` block with `@type: FAQPage` / `mainEntity: [Question → acceptedAnswer]`, built from the same data at build time, so page text and structured data cannot drift.
This is a separate block from `person.jsonld`, which stays untouched as the Person graph.

**Answer block placement.**
Opening paragraph of `ProfileSection`, before the existing lead paragraph: front-loaded, self-contained, liftable.
No reveal-animation gating of the text content.

### Static-HTML-facts audit + CI guard

One-off audit during execution: build `web/dist`, inspect raw HTML (no JS) for the core fact set - name, headline, employers, degrees, publication titles, project names - and fix any gap found.
Then a permanent pytest asserting two properties of `web/dist/index.html`:

1. **Public tier present:** the core facts appear in the raw built HTML (the ATS-guard pattern applied to the website).
2. **Deep tier absent:** a sentinel string from the `master-cv.example/` vocabulary does not appear, keeping the twin-exclusive tier provably off the public surface.

The test requires a web build.
`pages.yml` runs on main only, so the guard gets its own `ci.yml` job (like `ats-guard`): build `web/dist`, run the audit pytest, on every PR.

### Off-repo runbook (Wikidata + Scholar)

Committed as `docs/runbooks/2026-07-wikidata-entity.md`:

1. Notability self-check anchored on published DOI-bearing papers + ORCID.
2. Create the item from Jin-Ho's own Wikidata account.
3. Property list: instance-of human (P31), occupation, field of work (P101), ORCID iD (P496), GitHub username (P2037), official website (P856), country of citizenship - each statement referenced to a published source.
4. Explicit exclusion list: no birth date, employer, or alma mater; documented so a future session does not "helpfully" enrich the item.
5. Final step: paste the Q-ID URL into `personal.yaml` links, rerun renderers, regenerate snapshots.

Google Scholar needs no runbook; the URL lands in `personal.yaml` during execution.

### What FAQ does NOT touch

FAQ is a web-surface feature only.
It stays out of the PDF, `resume.json`, `person.jsonld`, `cv-*.txt`, and the twin chat context (the twin already knows everything in `content/`; feeding it its own FAQ adds nothing).

### Error handling

- Malformed `faq.yaml` (duplicate ids, missing `de`, empty strings) fails `just validate` loudly.
- A missing `faq.yaml` is a hard loader error, same as every other content file.
- The audit test fails CI if a core fact leaves static HTML or a deep-tier sentinel enters it.

### Testing (TDD throughout)

- Schema-validation tests with fixture YAML (valid, duplicate-id, missing-language, empty-answer cases).
- Loader test for the new `faq` key.
- Regenerated golden snapshots: web `content.*.json`, `cv-*.txt`, `resume.json` (diff eyeballed).
- A test that parses the FAQPage `ld+json` out of built HTML and validates its shape.
- The static-facts audit pytest (both directions).
- `_network_for` mapping test for the two new keys.
- Playwright visual pass on the rendered `<details>` section (local screenshot loop).

## Execution order

1. Repo work: schema + content files → loader → renderers/components → audit test → snapshots.
2. Off-repo (parallel, Jin-Ho's own accounts): Scholar URL immediately; Wikidata item via runbook, Q-ID wired in when it exists.
3. Standard phase close: plan's final task updates the CLAUDE.md phasing table (Phase 14 row); `--no-ff` merge closes #113 via the linked branch.

## Non-goals

- Any further `llms.txt` investment (proven inert).
- `robots.txt` changes (already correct: `User-agent: * / Allow: /`).
- FAQ automation or periodic regeneration from the twin log.
- Per-project answer blocks.
- A separate `/faq` route.
- Adding FAQ content to non-web renderers or the twin context.
