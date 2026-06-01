# Issue #46 — Variant-aware publication depth (web + plain text + PDF aggregate) — Design

**Status:** Approved design (Option B + scope forks resolved 2026-06-01). Ready for implementation plan.

**Issue:** [#46](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/46) — `feat(variants): variant-aware publication depth (Selected vs full)`.

**Goal:** Make the publication section vary by positioning target across the human-facing renderers — the academic variant (`comp-bio`) foregrounds the full per-paper list; the bridge/industry variants (`bridge`, `ds-ml`) show a derived one-line aggregate summary + ORCID pointer instead. "De-emphasize, don't delete."

**Supersedes:** the PDF behavior shipped in #43 (PR #52). #43 gave `bridge`/`ds-ml` a verbatim *first+shared* subset under a "Selected Publications" heading. #46 replaces that subset with the aggregate line and reverts the heading to plain "Publications". The #43 full-list renderer (per-paper loop) is **reused** for `comp-bio`.

---

## Motivation

SOTA academia→industry CV guidance is *de-emphasize-but-don't-delete*: an industry reader doesn't want 15 radiation-biophysics papers, but the publication record is still a credibility signal. So industry variants get a compact, ATS-parseable, ORCID-verifiable summary, while the academic variant keeps the full list. The numbers in the summary mirror the website authorship pie (6 first / 3 shared / 6 co-author = 15).

## Decisions (locked)

| Renderer | `comp-bio` | `bridge` / `ds-ml` |
|---|---|---|
| **PDF** (Typst) | Full verbatim list (unchanged from #43 renderer) | Aggregate line + ORCID pointer. Heading reverts to plain "Publications" / "Publikationen". |
| **Plain text** | Full verbatim list (current behavior) | Aggregate line + ORCID pointer (full `https://orcid.org/...` URL). |
| **Web** | Charts + full grouped list | Charts **stay visible** + aggregate line + ORCID pointer; only the verbose per-paper grouped list is hidden. |
| **JSON Resume / JSON-LD** | Full 15 structured records | Full 15 structured records — **unchanged**, target-independent (collapsing structured records into prose would be lossy). |

**Web charts rationale:** the authorship pie *is* the 6/3/6 aggregate, visually, and the cumulative chart is the Phase-9 centerpiece — so on the web the charts always show; only the per-paper list is variant-gated.

**Default (no-JS / bridge) web state:** charts + aggregate visible, full list `hidden`. Structured publication data for crawlers is already covered by the JSON-LD `@graph` (all 15), so hiding the verbose list by default has no SEO cost.

## Aggregate copy (from the agreed issue comment)

**EN:** `15 peer-reviewed publications — 6 first-author, 3 shared-first, 6 co-author (2017–2021), in radiation biophysics & super-resolution DNA-repair imaging.` + pointer `Full list & metrics: <orcid>`

**DE:** `15 begutachtete Publikationen — 6 als Erstautor, 3 geteilte Erstautorenschaft, 6 als Co-Autor (2017–2021), in Strahlenbiophysik & Super-Resolution-Bildgebung der DNA-Reparatur.` + pointer `Vollständige Liste: <orcid>`

The **numbers** (`total`, `first`, `shared`, `coauthor`) and the **year span** are *derived* (never hardcoded). The editorial prose, role wording, domain phrase, and word order live in `content/labels.yaml` per language.

### Content-accuracy notes (please confirm at review)

Verified against the live bib (`python -c` over `bib_loader`):
- `total=15`, `first=6`, `shared=3`, `coauthor=6` (middle/last/corresponding folded into co-author; live data has only `middle`).
- The lone 2025 entry is **applied, first-author** (`category: applied`). So:
  1. `first=6` **includes** the 2025 applied piece; the `(2017–2021)` span is derived from **research-category** years only, so it intentionally does not cover that one entry.
  2. The agreed wording says "15 **peer-reviewed** publications" — but one of the 15 is the applied 2025 piece. If that piece is not peer-reviewed, "peer-reviewed" slightly overclaims. Because the prose lives in `labels.yaml`, the word is a one-line content edit. **Flagging for your call** — keep "peer-reviewed" as agreed, or soften (e.g. "15 publications").

## Architecture — shared policy module

New file **`scripts/publications.py`** — the single home for variant publication policy + the aggregate, imported by `pdf/build.py`, `scripts/render_web_data.py`, and `scripts/render_text.py`. (Until #46, depth was a PDF-only concern living in `pdf/build.py: select_publications`; now that web + text also vary, the policy is genuinely shared and moves out of the PDF build path. The machine formats deliberately do **not** import it.)

```python
"""Variant-aware publication rendering policy + aggregate summary.

Shared by the PDF (pdf/build.py), website (scripts/render_web_data.py) and
plain-text (scripts/render_text.py) renderers so all three agree on (a) which
targets show the full per-paper list vs. a one-line aggregate, and (b) the exact
wording of that aggregate. The machine formats (JSON Resume, JSON-LD) bypass this
and always emit the full structured list.
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.bib_loader import Publication, authorship_counts

_COAUTHOR = ("middle", "last", "corresponding")  # everything that isn't first/shared
EN_DASH = "–"


def publication_mode(target: str) -> str:
    """"full" for the academic variant, "aggregate" for everyone else.

    comp-bio foregrounds the verbatim list; bridge/ds-ml collapse it to a derived
    summary line + ORCID pointer (de-emphasize-don't-delete).
    """
    return "full" if target == "comp-bio" else "aggregate"


@dataclass(frozen=True)
class PublicationSummary:
    total: int
    first: int
    shared: int
    coauthor: int
    year_start: int
    year_end: int


def publication_summary(pubs: list[Publication]) -> PublicationSummary:
    """Derive aggregate counts + research-year span from the full publication list.

    Counts cover all publications; ``coauthor`` folds middle/last/corresponding
    into one bucket. The span is taken from research-category entries only, so the
    lone applied piece does not stretch the stated research period.
    """
    counts = authorship_counts(pubs)
    research_years = [p.year for p in pubs if p.category == "research"] or [p.year for p in pubs]
    return PublicationSummary(
        total=len(pubs),
        first=counts.get("first", 0),
        shared=counts.get("shared", 0),
        coauthor=sum(counts.get(k, 0) for k in _COAUTHOR),
        year_start=min(research_years),
        year_end=max(research_years),
    )


def format_publication_summary(template: str, pubs: list[Publication]) -> str:
    """Fill a resolved (single-language) label template with derived figures.

    The template owns the prose + per-language word order; only numbers and the
    span are substituted, so counts are never hardcoded.
    """
    s = publication_summary(pubs)
    span = f"{s.year_start}{EN_DASH}{s.year_end}"
    return template.format(
        total=s.total, first=s.first, shared=s.shared, coauthor=s.coauthor, span=span
    )
```

## `content/labels.yaml` changes

Remove the now-unused `publications_selected` key (no variant uses a "Selected" heading anymore). Add a `publications` block with the aggregate template + pointer label (both LangStrings; `{…}` are Python `str.format` placeholders, untouched by `resolve_langstrings`):

```yaml
sections:
  # … unchanged …
  publications:          { en: "Publications",          de: "Publikationen" }
  # publications_selected:  <-- DELETED (obsolete after #46)
  # …

publications:
  summary:
    en: "{total} peer-reviewed publications — {first} first-author, {shared} shared-first, {coauthor} co-author ({span}), in radiation biophysics & super-resolution DNA-repair imaging."
    de: "{total} begutachtete Publikationen — {first} als Erstautor, {shared} geteilte Erstautorenschaft, {coauthor} als Co-Autor ({span}), in Strahlenbiophysik & Super-Resolution-Bildgebung der DNA-Reparatur."
  full_list_pointer:
    en: "Full list & metrics:"
    de: "Vollständige Liste:"
```

## PDF renderer

**`pdf/build.py: prepare_data`** — drop `select_publications` entirely; branch on `publication_mode`:

```python
from scripts.publications import publication_mode, format_publication_summary

# inside prepare_data, after resolve_langstrings:
mode = publication_mode(target)
sections = resolved["labels"]["sections"]
resolved["publications_mode"] = mode
resolved["publications_heading"] = sections["publications"]  # always plain now
if mode == "aggregate":
    pub_labels = resolved["labels"]["publications"]
    resolved["publications_summary"] = format_publication_summary(
        pub_labels["summary"], resolved.get("publications", [])
    )
    resolved["publications_pointer"] = pub_labels["full_list_pointer"]
else:
    resolved["publications_summary"] = None
    resolved["publications_pointer"] = None
# resolved["publications"] keeps the full list; the aggregate Typst branch ignores it.
```

**`pdf/templates/publications.typ`** — branch on mode; the `else` branch is the #43 per-paper loop verbatim. New signature takes the whole `data` (matching `sidebar(data, …)`'s precedent):

```typst
#import "../styles.typ": *

#let publications(data) = {
  section-heading(data.publications_heading)

  if data.publications_mode == "aggregate" {
    [#data.publications_summary]
    linebreak()
    let orcid = data.personal.links.orcid
    let shown = orcid.replace("https://", "").replace("http://", "")
    text(size: size-small, fill: muted)[#data.publications_pointer #link(orcid)[#text(fill: accent)[#shown]]]
  } else {
    let family = data.personal.name.family
    for (i, p) in data.publications.enumerate() {
      // … #43 author/year/title/venue loop, unchanged …
    }
  }
}
```

**`pdf/templates/cv.typ`** — call site becomes `publications(data)` (was `publications(data.publications, data.publications_heading, data.personal.name.family)`).

## Plain-text renderer

**`scripts/render_text.py`** — `render()` branches per target; full URL for the pointer (consistent with how DOIs render as `https://doi.org/…`):

```python
from scripts.publications import publication_mode, format_publication_summary

def _publications_aggregate(content: dict, pubs: list[Publication]) -> str:
    summary = format_publication_summary(content["labels"]["publications"]["summary"], pubs)
    pointer = content["labels"]["publications"]["full_list_pointer"]
    orcid = content["personal"]["links"]["orcid"]
    return f"{_wrap(summary)}\n{pointer} {orcid}"

# in render():
pub_body = _publications(pubs) if publication_mode(target) == "full" else _publications_aggregate(content, pubs)
# … _section(L["publications"][lang], pub_body) …
```

The text `SECTION_LABELS["publications"]` is already plain "PUBLICATIONS"/"PUBLIKATIONEN" — no heading change.

## Web renderer

**`scripts/render_web_data.py`** — inject the (target-independent) aggregate strings into the bridge content JSON, and add a `publications_mode` override for `comp-bio` only:

```python
from scripts.publications import publication_mode, format_publication_summary

# after building bridge_resolved, before _dump:
pub_labels = bridge_resolved["labels"]["publications"]
bridge_resolved["publications_aggregate"] = {
    "summary": format_publication_summary(pub_labels["summary"], bridge_resolved["publications"]),
    "pointer": pub_labels["full_list_pointer"],
}

# in the variant loop:
overrides = _extract_overrides(bridge_resolved, variant_resolved)
mode = publication_mode(target)
if mode != publication_mode("bridge"):     # only comp-bio differs from the aggregate default
    overrides["publications_mode"] = mode
variants_dict[target] = overrides
```

**`web/src/components/PublicationsList.astro`** — keep the charts always visible; render the aggregate block (visible by default) and wrap the existing grouped list in a `hidden` full block:

```astro
interface Props {
  publications: Publication[];
  aggregate: { summary: string; pointer: string };
  orcid: string;
  lang: Lang;
}
const { publications, aggregate, orcid, lang } = Astro.props;
const orcidDisplay = orcid.replace(/^https?:\/\//, "");
```
```html
<section id="publications" class="py-6">
  <h2 class="eyebrow mb-4">{sectionLabel[lang]}</h2>
  <div class="flex flex-col gap-2 md:flex-row md:items-center md:gap-8">
    <div class="shrink-0"><PublicationsChart publications={publications} lang={lang} /></div>
    <div class="flex-1 min-w-0"><PublicationsCumulative publications={publications} lang={lang} /></div>
  </div>

  <div data-cv-pub="aggregate" class="mt-4 text-sm text-[var(--muted)]">
    <p>{aggregate.summary}</p>
    <p class="mt-1 text-xs text-[var(--faint)]">
      {aggregate.pointer}{" "}
      <a href={orcid} target="_blank" rel="noopener noreferrer"
         class="underline decoration-dotted underline-offset-2 hover:text-[var(--text)]">{orcidDisplay}</a>
    </p>
  </div>

  <div data-cv-pub="full" hidden class="mt-4">
    {/* existing typeOrder→grouped per-paper list, unchanged */}
  </div>
</section>
```

**`web/src/components/TargetSwitcher.astro`** — extend the `Variant` interface with `publications_mode?: "full" | "aggregate"`, and toggle the two blocks inside `apply()` (charts untouched):

```js
const pubMode = (overrides && overrides.publications_mode) || "aggregate";
const fullBlock = document.querySelector('[data-cv-pub="full"]');
const aggBlock  = document.querySelector('[data-cv-pub="aggregate"]');
if (fullBlock) fullBlock.hidden = pubMode !== "full";
if (aggBlock)  aggBlock.hidden  = pubMode !== "aggregate";
```

**`web/src/pages/index.astro` + `web/src/pages/de/index.astro`** — pass the new props:
```astro
<PublicationsList publications={data.publications}
                  aggregate={data.publications_aggregate}
                  orcid={data.personal.links.orcid} lang="en" />
```

**`web/src/types/content.ts`** — add `publications_aggregate: { summary: string; pointer: string }` to `ContentData`; add `publications: { summary: string; full_list_pointer: string }` to `Labels`.

## What #46 removes

- `pdf/build.py: select_publications` (function + its unit/integration tests).
- `content/labels.yaml: sections.publications_selected`.
- The "Selected Publications" heading path (`publications_heading` is now always the plain label).

## Testing strategy (TDD)

- **`tests/test_publications.py`** (NEW): `publication_mode` (comp-bio→full, bridge/ds-ml→aggregate); `publication_summary` on synthetic pubs (count buckets, coauthor folding, research-only span); `format_publication_summary` (placeholder fill, en-dash span); live-bib assertions (`total=15, first=6, shared=3, coauthor=6, span=2017–2021`) — derived, not hardcoded.
- **`tests/test_pdf_publications.py`** (REWORK): remove `select_publications` tests; assert `prepare_data` sets `publications_mode`/`publications_summary`/`publications_pointer`/plain `publications_heading` per target and language; PDF-text test — bridge PDF contains aggregate markers (`orcid.org/0009…`, the derived counts) and omits a middle-author title; comp-bio PDF contains a middle-author title.
- **`tests/test_render_text.py`**: comp-bio contains a known paper title; bridge contains the aggregate summary substring + the full ORCID URL and omits the middle-author title.
- **`tests/test_render_web_data.py`**: `content.{lang}.json` carries `publications_aggregate.summary`/`.pointer`; `variants[comp-bio].publications_mode == "full"`; `ds-ml` has no `publications_mode` key.
- `just validate && just test && just lint` green; `just web-build` succeeds.

## Out of scope

- JSON Resume / JSON-LD changes (stay full, structured).
- Embedding the website charts in the PDF (rejected earlier: ATS-hostile, non-standard, not Typst-reusable).
- Any change to `content/publications.bib` content (no new data entry — `authorship`/`category`/`year` already exist).

## Files touched

| File | Change |
|---|---|
| `scripts/publications.py` | **NEW** — shared policy + aggregate |
| `content/labels.yaml` | −`publications_selected`; +`publications` block |
| `pdf/build.py` | −`select_publications`; branch on `publication_mode` |
| `pdf/templates/publications.typ` | branch full vs aggregate; `publications(data)` |
| `pdf/templates/cv.typ` | call `publications(data)` |
| `scripts/render_text.py` | per-target aggregate branch |
| `scripts/render_web_data.py` | inject aggregate; `publications_mode` override |
| `web/src/components/PublicationsList.astro` | charts always; aggregate + full blocks |
| `web/src/components/TargetSwitcher.astro` | toggle pub blocks; `Variant` type |
| `web/src/pages/index.astro`, `…/de/index.astro` | pass new props |
| `web/src/types/content.ts` | `ContentData` + `Labels` additions |
| `tests/test_publications.py` | **NEW** |
| `tests/test_pdf_publications.py`, `test_render_text.py`, `test_render_web_data.py` | reworked/extended |
| `CLAUDE.md` | add `scripts/publications.py` to Layout; confirm phasing table unchanged (maintenance item) |
