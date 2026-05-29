# DOI fields + outbound links — design spec

**Issue:** [#26](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/26) · **Date:** 2026-05-29 · **Branch:** `issue-26-doi-fields`

## Goal

Give every publication that has a public DOI a `doi` field in `content/publications.bib`, and expose it as an authoritative outbound link (`https://doi.org/<doi>`) across the web, plain-text, JSON Resume, and JSON-LD renderers. This is an SEO signal (cross-references the corpus with the citation graph), a reader-trust signal (a clickable, verifiable record), and fills a slot the machine-readable formats already expect (`publications[].url`, `ScholarlyArticle.sameAs`).

This is a standalone issue, not a new phase — all six phases are complete.

## Non-goals

- **No fabricated DOIs.** Entries without a public DOI leave the field absent. Never link a wrong DOI.
- **PDF is out of scope** — confirmed the Typst template (`pdf/templates/cv.typ`) renders no publications section at all, so there is nothing to link there.
- No `identifier`/`PropertyValue` modelling in JSON-LD (see Decisions).
- No new *required* field: `doi` is optional everywhere.

## Decisions (resolved during brainstorming)

1. **DOI sourcing — look up, then human-verify.** Candidates are pulled from the author's public **ORCID** record (authoritative) cross-checked against the **Crossref REST API** by title/author. A verification table (`key → proposed DOI → confidence → source`) is presented; only user-confirmed DOIs are written into the `.bib`. This satisfies the no-fabrication non-goal with a human gate.
2. **Web display — DOI on the meta line, showing the bare DOI as the link text.** Title stays plain (consistent typography whether or not an entry has a DOI). The DOI appears appended to the existing `venue · year · authorship` line as `· <a>10.xxxx/yyy</a>`, href `https://doi.org/<doi>`. Showing the real DOI (not a generic "DOI ↗" label or a truncated value) is itself the trust signal.
3. **JSON-LD — `sameAs` only.** `sameAs: ["https://doi.org/<doi>"]` is exactly how search engines reconcile an entity with its authoritative external record, which is the SEO goal. `identifier`/`PropertyValue` adds nothing for discovery (YAGNI).
4. **Ordering — code-first TDD, content last.** Renderer plumbing is built and tested against fixture `.bib` data so it does not wait on the slow human-verification loop; real DOIs land as a final data-only commit. End state is identical to content-first.
5. **Commits/branch — three atomic commits on `issue-26-doi-fields`, merged via PR** (matches repo convention: atomic commits, PR merges like #29–#31). Branch created with `gh issue develop` to link it to the issue.

## Architecture & touchpoints

### 1. Data model — `scripts/bib_loader.py`
- Add `doi: str | None` to the `Publication` dataclass, positioned after `venue`, before `raw`.
- Extract via `fields.get("doi")`, **normalized**: strip surrounding whitespace and any pasted resolver prefix (`https://doi.org/`, `http://dx.doi.org/`, `doi:`) so the stored value is the bare `10.xxxx/yyy`. Renderers prepend the resolver URL.
- `doi` stays optional — no change to the required-field loop.

### 2. Validation guard — `scripts/validate.py` (via the loader)
- In `_parse_entry`: if `doi` is present but does not match `^10\.\d{4,9}/\S+$` (case-insensitive), raise `ValueError`. This is surfaced by the existing `_validate_publications`, which already round-trips the bib through `load_publications`. Absent DOI is always valid.

### 3. Renderers

| Renderer | Change |
|---|---|
| Web JSON — `scripts/render_web_data.py` | **None.** `dataclasses.asdict` already serializes every dataclass field (then drops `raw`), so `doi` flows to `content.{en,de}.json` automatically. Covered by a test, not a code change. |
| TS type — `web/src/types/content.ts` | Add `doi: string \| null` to the `Publication` interface. |
| Web component — `web/src/components/PublicationsList.astro` | On the meta `<p>`, when `p.doi`, append ` · ` + `<a href={"https://doi.org/" + p.doi} target="_blank" rel="noopener noreferrer">{p.doi}</a>`. Title rendering unchanged. |
| Plain text — `scripts/render_text.py` | In `_publications`, when `p.doi`, append a third line `  https://doi.org/{p.doi}` to the entry block. The publications block does not run through `_wrap`, so the URL stays intact on one line. |
| JSON Resume — `scripts/render_jsonresume.py` | In `_publications`, include `"url": f"https://doi.org/{p.doi}"` only when `p.doi` is set (key omitted otherwise). |
| JSON-LD — `scripts/render_jsonld.py` | In `_publications`, add `item["sameAs"] = [f"https://doi.org/{p.doi}"]` when `p.doi` is set. |

### 4. Content — `content/publications.bib`
Look up → verify → write, per Decision 1. Add `doi = {10.xxxx/yyy}` to each confirmed entry.

Expected to **legitimately lack** a DOI (field left absent):
- Conference contributions: `lee2021_degbs`, `lee2019_conrad`, `lee2018_dro`
- Self-published 2025 chapter: `lee2025_marketing_automation`

Best-effort / uncertain (look up, accept absence if none found):
- `lee2019_combofish` (OBM Genetics), `lee2021superres_dna_repair` (2021 book chapter)

## Testing (TDD, pytest)

- **`tests/test_bib_loader.py`** — `doi` extracted when present; `None` when absent; resolver-prefix/whitespace normalized to bare DOI; a malformed `doi` raises `ValueError` (mirrors the existing `test_missing_authorship_field_raises` fixture pattern).
- **`tests/test_validate.py`** — a fixture bib with a malformed `doi` produces a `FileError`; a valid/absent `doi` does not.
- **`tests/test_render_web_data.py` / `test_build_data.py`** — the `doi` key is serialized into the content JSON for a DOI entry.
- **`tests/test_render_text.py`** — the `https://doi.org/<doi>` line is present for a DOI entry and absent otherwise.
- **`tests/test_render_jsonresume.py`** — `publications[].url` equals the `doi.org` URL when present and the key is omitted otherwise; output still validates against `tests/fixtures/jsonresume-schema.json`.
- **`tests/test_render_jsonld.py`** — the `ScholarlyArticle` node carries `sameAs` with the `doi.org` URL.

**Known coverage gap (stated honestly):** the repo has no JS/Astro test harness (tests are pytest-only). The `PublicationsList.astro` change is therefore verified by (a) the serialized-JSON contract test above, (b) `just web-build` succeeding, and (c) a visual check of the rendered list — not a component unit test.

## Sequencing & commits

1. **`bib_loader` + validation** — dataclass field, normalization, format guard, loader/validate tests.
2. **Renderers + tests** — TS type, `.astro` component, plain text, JSON Resume, JSON-LD, and their tests (against fixtures).
3. **Content** — verified real DOIs written into `publications.bib` (data-only commit).

`just validate && just test && just lint` green before the PR. Merge to `main` via PR.

## Done when (from the issue)

- Every publication with a public DOI has the field in `.bib`; DOI-less entries have no `doi` field.
- `https://jinholee.is-a.dev/` renders each DOI-bearing publication with a clickable `doi.org` link on the meta line.
- `dist/cv-en.txt` and `dist/cv-de.txt` include the DOI URLs.
- `dist/resume.json` includes `publications[].url` for DOI-linked entries.
- `dist/person.jsonld` includes the DOI as `sameAs` on each corresponding `ScholarlyArticle`.
- `just validate && just test && just lint` all green.
