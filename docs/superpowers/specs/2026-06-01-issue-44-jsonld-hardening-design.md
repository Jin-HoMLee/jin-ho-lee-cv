# Issue #44 — Harden JSON-LD structured data

**Issue:** [#44](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/44) (`bug`, size: M)

**Goal:** Fix the concrete JSON-LD defects so the document is a clean, top-level `@graph` of `@id`-linked schema.org entities optimized for **AI/LLM entity resolution** (not SEO rich results, which Google does not surface for Person).

## Why

Verified defects in `dist/person.jsonld` (and `scripts/render_jsonld.py`):
1. `@graph` (publications + projects) is nested as a **property of the Person node** rather than a top-level graph of `@id`-linked entities.
2. `alumniOf` lists **"Heidelberg University" twice** (two education entries, same institution).
3. `worksFor` absent / null — no open-ended role (latest ended 2025-07).
4. No `identifier` PropertyValue for ORCID; no per-article DOI `identifier` (DataCite / science-on-schema.org prefer this over a bare `sameAs`).
5. No `hasOccupation`; `knowsAbout` is 45 raw skill items (over-long, some cryptic).

## Decisions (user, 2026-06-01)

- **`worksFor`: omit.** No current employer is claimed (honest — between roles). `_works_for` becomes dead code and is removed. **No employment-history graph is added** in #44 (out of scope; experience is not currently in the JSON-LD and stays out — a possible future enhancement).
- **`knowsAbout`: curated list in content.** A new `knowsAbout` array on `content/personal.yaml` (single source of truth), replacing the 45-item skills derivation. Draft (~15, language-neutral technical topics) below — to confirm at the spec-review gate.
- **`hasOccupation`: bridge headline.** Two `Occupation` nodes derived from `personal.headline` ("Bioinformatics · Data Science"), split on "·".

## Scope & design

### `scripts/render_jsonld.py` — top-level `@graph` of `@id`-linked entities

New document shape:
```json
{
  "@context": "https://schema.org",
  "@graph": [ <Person>, <ScholarlyArticle…>, <CreativeWork…> ]
}
```
- **Person node** (`@id` = ORCID URI, the canonical entity identifier):
  - keeps `name`, `url`, `image`, `email`, `jobTitle`, `description`, `address`, `sameAs`;
  - `alumniOf` — **deduped** by institution name (order-preserving);
  - `knowsAbout` — the curated content list;
  - `hasOccupation` — `[{"@type": "Occupation", "name": "Bioinformatics"}, {"@type": "Occupation", "name": "Data Science"}]` (from the bridge headline);
  - `identifier` — `{"@type": "PropertyValue", "propertyID": "ORCID", "value": "<orcid-url>"}`;
  - `award` (unchanged, when present);
  - **no `worksFor`.**
- **ScholarlyArticle nodes** (one per publication):
  - `@id` = DOI URL when present, else `"{PAGES_BASE_URL}/#publication-{i}"` (stable fragment);
  - `name`, `datePublished`, `isPartOf` (when venue);
  - `author` — list of `{"@type": "Person", "name": …}`, **except** the author matching `startswith("Lee, J")` (him — reliable since it's his own bib) becomes `{"@id": "<orcid>"}` so the work links to the Person node for entity resolution; the literal `"others"` author is dropped or rendered as-is per current behavior (keep current handling — do not invent);
  - `sameAs` (DOI URL, kept) **and** `identifier` `{"@type": "PropertyValue", "propertyID": "DOI", "value": doi}`.
- **CreativeWork nodes** (projects): `@id` = `"{PAGES_BASE_URL}/projects/{id}/"` (the existing url, promoted to `@id`); keep `name`, `url`, `description`, `dateCreated`, `keywords`; add `creator: {"@id": "<orcid>"}` linking to the Person.

`to_jsonld` returns the `{"@context", "@graph": [...]}` wrapper. The Person is built by a `_person(content, pubs)` helper; `_publications`/`_projects` gain `@id` + author/creator links.

### `content/personal.yaml` + `schema/cv.schema.json` — curated `knowsAbout`

- Add to `personal.yaml` a top-level `knowsAbout` list (language-neutral strings). **Draft for review:**
  ```yaml
  knowsAbout:
    - Bioinformatics
    - Cancer Genomics
    - Computational Biology
    - Data Science
    - Machine Learning
    - Next-Generation Sequencing
    - RNA-Seq Analysis
    - Variant Calling
    - HLA Typing
    - Neoantigen Discovery
    - Immunoinformatics
    - Super-Resolution Microscopy
    - Spatial Point-Pattern Analysis
    - Cloud Data Engineering
    - Bioimage Analysis
  ```
- Add to the schema `personal` definition (which is `additionalProperties: false`):
  ```json
  "knowsAbout": { "type": "array", "items": { "type": "string" }, "minItems": 1 }
  ```
  Optional (not in `required`) — keeps other content valid if absent; renderer falls back to `[]` if missing.
- `render_jsonld._knows_about(content)` reads `content["personal"].get("knowsAbout", [])` instead of walking skills.

### Docs reframe

- Module docstring / a comment in `render_jsonld.py` notes the purpose: **machine-readable identity for AI/LLM entity resolution and knowledge-graph ingestion**, explicitly *not* SEO rich results (Google has no Person rich result; dropped `EstimatedSalary` June 2025). Add the same framing line to this spec's intro (done).

### Tests (`tests/test_render_jsonld.py`) + snapshot (#42)

- **Remove** the #42 `test_works_for_*` characterization tests (behavior intentionally gone) and any assertion of the old nested `@graph`/`worksFor`/duplicate-`alumniOf`/skills-`knowsAbout` shape.
- **Add** TDD tests for the new shape:
  - root has `@graph`; no top-level Person properties besides `@context`/`@graph`;
  - Person node `@id` == ORCID URL; has `identifier` (ORCID PropertyValue), `hasOccupation` (2 occupations from headline), curated `knowsAbout` (== `personal.knowsAbout`), **no** `worksFor`;
  - `alumniOf` has no duplicate institution names;
  - each ScholarlyArticle has `@id`, a DOI `identifier` when the pub has a DOI, and links the author matching `"Lee, J"` to the Person `@id`;
  - each project CreativeWork has `@id` + `creator: {"@id": orcid}`.
- **Re-baseline** the `person.jsonld` golden snapshot: `just snapshots-update` (only `test_person_jsonld.json` changes), eyeball the diff. The web build copies `dist/person.jsonld` → `web/public/`; BaseLayout raw-imports it — a top-level `@graph` is valid inline JSON-LD, **no web component change**.

## Out of scope

- Employment-history nodes in the graph (worksFor omitted, not replaced).
- Variant-aware JSON-LD (stays bridge/en, like JSON Resume).
- Any change to JSON Resume / plain text / PDF.

## Testing / verification

- TDD: new-shape tests first (watch fail against current renderer), implement, green.
- `just validate` (schema accepts the new `knowsAbout`; content validates) · `just test` (incl. re-baselined snapshot) · `just lint` green.
- Manually eyeball `dist/person.jsonld` and validate it as JSON-LD (paste into a JSON-LD playground / `pyld` expand if available) — the `@graph` expands to discrete `@id`-keyed nodes.

## Commit plan (atomic)

1. `feat(content): #44 add curated knowsAbout topics + schema` (personal.yaml + schema)
2. `feat(jsonld): #44 top-level @graph, @id-linked entities, identifier, hasOccupation; dedupe alumniOf; drop worksFor` (render_jsonld + tests, TDD)
3. `test: #44 re-baseline person.jsonld golden snapshot`
4. `docs: #44 reframe JSON-LD value as LLM entity-resolution` (docstring/comment, if not folded into #2)

(Spec committed first.)
