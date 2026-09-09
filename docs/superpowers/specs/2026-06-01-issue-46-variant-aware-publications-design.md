# Issue #46 — Variant-aware publication depth (web + plain text + PDF aggregate) — Design

**Status:** Approved design (Option B + scope forks resolved 2026-06-01). Implemented in the current change; the source files and labels referenced below own the final behavior.

**Issue:** [#46](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/46) — `feat(variants): variant-aware publication depth (Selected vs full)`.

**Goal:** Make the publication section vary by positioning target across the human-facing renderers — the academic variant (`comp-bio`) foregrounds the full per-paper list; the bridge/industry variants (`bridge`, `ds-ml`) show a derived one-line aggregate summary + ORCID pointer instead. "De-emphasize, don't delete."

**Supersedes:** the PDF behavior shipped in #43 (PR #52). #43 gave `bridge`/`ds-ml` a verbatim *first+shared* subset under a "Selected Publications" heading. #46 replaces that subset with the aggregate line and reverts the heading to plain "Publications". The #43 full-list renderer (per-paper loop) is **reused** for `comp-bio`.

---

## Motivation

SOTA academia→industry CV guidance is *de-emphasize-but-don't-delete*: an industry reader doesn't need all 15 bibliography records foregrounded, but the publication record is still a credibility signal. The inventory contains 14 research records plus 1 applied/off-domain record. Industry variants get a compact, ATS-parseable, ORCID-verifiable research summary, while the academic variant keeps the full list. The website authorship pie covers all records (6 first / 3 shared / 6 co-author = 15).

## Decisions (locked)

| Renderer | `comp-bio` | `bridge` / `ds-ml` |
|---|---|---|
| **PDF** (Typst) | Full verbatim list (unchanged from #43 renderer) | Aggregate line + ORCID pointer. Heading reverts to plain "Publications" / "Publikationen". |
| **Plain text** | Full verbatim list (current behavior) | Aggregate line + ORCID pointer (full `https://orcid.org/...` URL). |
| **Web** | All-record charts + full category-grouped list | All-record charts **stay visible** + research aggregate line + ORCID pointer; only the verbose per-paper category-grouped list is hidden. |
| **JSON Resume / JSON-LD** | Full 15 structured records | Full 15 structured records — **unchanged**, target-independent (collapsing structured records into prose would be lossy). |

**Web charts rationale:** the authorship pie *is* the all-record 6/3/6 aggregate, visually, and the cumulative chart is the Phase-9 centerpiece. Both charts therefore remain visible for every target and their captions explicitly identify the 15 bibliography records as 14 research records plus 1 applied/off-domain record. Only the per-paper list is variant-gated.

**Default (no-JS / bridge) web state:** all-record charts + research aggregate visible, full list `hidden`. The StatBand uses the 11 peer-reviewed research-record count. Structured publication data for crawlers is already covered by the JSON-LD `@graph` (all 15), so hiding the verbose list by default has no SEO cost.

## Aggregate copy (honest, type-segmented — resolved 2026-06-01)

The exact bilingual aggregate templates and pointer labels are owned by
`content/labels.yaml`. They communicate 11 peer-reviewed research publications
(10 articles plus 1 research book chapter), the 2/3/6 peer-reviewed authorship
breakdown, 3 research conference contributions, 1 applied/off-domain record, the
14 research-record subtotal, the 15-record bibliography total, and the research
span. Renderers consume the resolved labels; they do not own parallel copies of
this wording.

All figures are *derived* from `bib_loader` (never hardcoded); only the editorial
prose, role wording, domain phrase, the "first-author conference contributions"
descriptor, and per-language word order live in `content/labels.yaml`.

### What counts as "peer-reviewed" (verified against the live bib)

The full record is **15** entries: 10 journal articles, 1 research book chapter,
1 applied/off-domain book chapter, and 3 conference contributions. The aggregate
derives its research metrics from the **research** body (14; the lone 2025 applied
marketing book chapter is excluded from those metrics as off-domain) while
explicitly disclosing the applied record and all-record total. It distinguishes
peer-reviewed from conference work:

| Bucket | Rule | Count | first / shared / co-author |
|---|---|---|---|
| **Peer-reviewed** | research, `type ∈ {article, book-chapter}` | **11** (10 articles + the 2021 *Super-Resolution Radiation Biology* book chapter) | 2 / 3 / 6 |
| **Conference contributions** | research, `type == conference` | **3** | 3 / 0 / 0 (all first-author) |
| **Applied/off-domain** | excluded from research metrics; `category: applied` | **1** | — |

Peer-review is inferred from type: research **articles + book chapters are peer-reviewed**, **conference contributions are not** (per the author, 2026-06-01). The span `2017–2021` is the research-body min/max year. Everything ties out: 11 + 3 = 14 research items, plus 1 applied record = 15 total; peer-reviewed authorship 2 + 3 + 6 = 11. The descriptor "3 **first-author** conference contributions" is editorial in the label (true for all three current conference entries; a future non-first-author conference entry would be a one-line content edit).

## Architecture — shared policy module

New file **`scripts/publications.py`** is the single home for variant publication
policy and derived publication numbers. It is shared by the PDF, website, and
plain-text renderers; JSON Resume and JSON-LD deliberately continue to emit the
full structured list without importing this presentation policy.

The module's `PublicationSummary` owns the complete inventory and its scopes:
`total_records`, `research_records`, `peer_reviewed`, the article and research
book-chapter split, peer-reviewed authorship counts, conference count,
`applied_records`, all-record authorship counts, and the research year span.
`publication_metrics()` serializes the website subset needed by the charts and
StatBand. `format_publication_summary()` fills the aggregate template owned by
`content/labels.yaml`.

## `content/labels.yaml` changes

Remove the now-unused `publications_selected` key (no variant uses a "Selected"
heading anymore). The canonical `publications` block in `content/labels.yaml`
owns the bilingual aggregate template, pointer label, and the resolved
`research_label` / `applied_label` scope labels. Its `{...}` placeholders are
filled by `format_publication_summary()` after language resolution. Renderers must
consume these labels rather than defining parallel English/German copies.

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

**`pdf/templates/publications.typ`** — branch on mode. The full branch renders
the complete per-paper list, grouped under the resolved research/applied scope
labels; the aggregate branch renders the summary and ORCID pointer. The full list
uses compact inter-record spacing so the applied record does not leave avoidable
whitespace. The signature takes the whole `data` (matching `sidebar(data, …)`'s
precedent):

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
pub_body = (
    _publications(pubs, lang, content["labels"]["publications"])
    if publication_mode(target) == "full"
    else _publications_aggregate(content, pubs)
)
# … _section(L["publications"][lang], pub_body) …
```

The text `SECTION_LABELS["publications"]` is already plain "PUBLICATIONS"/"PUBLIKATIONEN" — no heading change.
The full list prefixes each category with the canonical resolved research or
applied label.

## Web renderer

**`scripts/render_web_data.py`** — inject the target-independent aggregate
strings and generated `publication_metrics` object into the bridge content JSON.
For this publication-depth feature, the `variants.json` payload is **not** touched:
which targets show the full list vs. the aggregate is a pure function of the target
name, so the client computes it (below) rather than carrying a `publications_mode`
field. At the time of this issue, the payload carried exactly four positioning fields;
Phase 8c later extended it with resolved Skills trees and an optional `hero_stack` - see
the [current Phase 8c design contract](2026-05-31-phase-8c-web-variants-design.md).

```python
from scripts.publications import format_publication_summary, publication_metrics

# after building bridge_resolved, before _dump:
bridge_resolved["publication_metrics"] = publication_metrics(
    bridge_resolved["publications"]
)
pub_labels = bridge_resolved["labels"]["publications"]
bridge_resolved["publications_aggregate"] = {
    "summary": format_publication_summary(pub_labels["summary"], bridge_resolved["publications"]),
    "pointer": pub_labels["full_list_pointer"],
}
```

**`web/src/components/PublicationsList.astro`** — keep the all-record charts
always visible; render the research aggregate block (visible by default) and
wrap the category-grouped full list in a `hidden` block. The component receives
the generated metrics and resolved labels so chart and list scope wording has a
single source.

```astro
interface Props {
  publications: Publication[];
  metrics: PublicationMetrics;
  aggregate: { summary: string; pointer: string };
  labels: Labels;
  orcid: string | null;
  scholar?: string | null;
  lang: Lang;
}
const { publications, metrics, aggregate, labels, orcid, scholar, lang } = Astro.props;
const orcidDisplay = orcid ? orcid.replace(/^https?:\/\//, "") : "";
```
The aggregate block uses `data-cv-pub="aggregate"` and links the available ORCID
and Google Scholar profiles. The full block uses `data-cv-pub="full"`, remains
hidden in the bridge default, and contains the category labels from
`labels.publications` followed by the type-grouped per-paper list.

**`web/src/components/TargetSwitcher.astro`** — toggle the two pre-rendered blocks inside `apply()` based on the target name (charts untouched). The full list shows only for `comp-bio`; the aggregate shows for everyone else, matching the default (bridge) server-rendered state. No `Variant` type change needed.

```js
// publications depth: comp-bio shows the verbatim list; bridge/ds-ml the aggregate.
const showFull = target === "comp-bio";
const fullBlock = document.querySelector('[data-cv-pub="full"]');
const aggBlock  = document.querySelector('[data-cv-pub="aggregate"]');
if (fullBlock) fullBlock.hidden = !showFull;
if (aggBlock)  aggBlock.hidden  = showFull;
```

**`web/src/pages/index.astro` + `web/src/pages/de/index.astro`** — pass the
aggregate, generated metrics, resolved labels, and profile links as props:
```astro
<PublicationsList publications={data.publications}
                  metrics={data.publication_metrics}
                  aggregate={data.publications_aggregate}
                  labels={data.labels}
                  orcid={data.personal.links.orcid}
                  scholar={data.personal.links.googlescholar} lang="en" />
```

**`web/src/lib/publicationScope.ts`** owns the bilingual chart scope captions and
total-record labels used by both charts. **`web/src/types/content.ts`** adds
`publication_metrics` to `ContentData`, and its `Labels.publications` type
exposes the resolved research/applied scope labels. The aggregate strings remain
under `ContentData.publications_aggregate`. There is no `Variant` change: the
switcher still derives depth from the target name.

## What #46 removes

- `pdf/build.py: select_publications` (function + its unit/integration tests).
- `content/labels.yaml: sections.publications_selected`.
- The "Selected Publications" heading path (`publications_heading` is now always the plain label).

## Testing strategy (TDD)

- **`tests/test_publications.py`** (NEW): `publication_mode` (comp-bio→full, bridge/ds-ml→aggregate); `publication_summary` on synthetic pubs (peer-reviewed = research articles+chapters, conference excluded from peer-reviewed, applied excluded entirely, coauthor folding, research-only span); `publication_metrics` (15 total, 14 research, 11 peer-reviewed, 1 applied, and all-record 6/3/6 authorship); `format_publication_summary` (placeholder fill, en-dash span); live-bib assertions (`peer_reviewed=11, pr_first=2, pr_shared=3, pr_coauthor=6, conferences=3, span=2017–2021`) — derived, not hardcoded.
- **`tests/test_pdf_publications.py`** (REWORK): remove `select_publications` tests; assert `prepare_data` sets `publications_mode`/`publications_summary`/`publications_pointer`/plain `publications_heading` per target and language; PDF-text test — bridge PDF contains aggregate markers (`orcid.org/0009…`, "11 peer-reviewed") and omits a middle-author title; comp-bio PDF contains a middle-author title.
- **`tests/test_render_text.py`**: comp-bio contains a known paper title; bridge contains the aggregate summary substring + the full ORCID URL and omits the middle-author title.
- **`tests/test_render_web_data.py`**: `content.{lang}.json` carries `publication_metrics` and `publications_aggregate.summary`/`.pointer` (and the exact top-level key-set includes both). `tests/test_render_web_data_variants.py` is **unchanged** — `publications_mode` is not in the variants payload (client derives it from the target).
- `just validate && just test && just lint` green; `just web-build` succeeds.

## Out of scope

- JSON Resume / JSON-LD changes (stay full, structured).
- Embedding the website charts in the PDF (rejected earlier: ATS-hostile, non-standard, not Typst-reusable).
- Any change to `content/publications.bib` content (no new data entry — `authorship`/`category`/`year` already exist).

## Files touched

| File | Change |
|---|---|
| `scripts/publications.py` | **NEW** — shared policy, aggregate, and website metrics |
| `content/labels.yaml` | −`publications_selected`; +`publications` block |
| `pdf/build.py` | −`select_publications`; branch on `publication_mode` |
| `pdf/templates/publications.typ` | branch full vs aggregate; `publications(data)` |
| `pdf/templates/cv.typ` | call `publications(data)` |
| `scripts/render_text.py` | per-target aggregate branch |
| `scripts/render_web_data.py` | inject `publication_metrics` and `publications_aggregate` into content JSON |
| `web/src/components/PublicationsList.astro` | all-record charts; aggregate + category-grouped full blocks |
| `web/src/components/PublicationsChart.astro` | render all-record authorship metrics and scope caption |
| `web/src/components/PublicationsCumulative.astro` | render all-record cumulative scope caption |
| `web/src/components/StatBand.astro` | show the 11 peer-reviewed research-record count |
| `web/src/lib/publicationScope.ts` | shared bilingual chart scope formatting |
| `web/src/components/TargetSwitcher.astro` | toggle pub blocks (derive from target) |
| `web/src/pages/index.astro`, `…/de/index.astro` | pass new props |
| `web/src/types/content.ts` | `ContentData.publication_metrics` and `publications_aggregate`; resolved publication labels |
| `tests/test_publications.py` | **NEW** |
| `tests/test_pdf_publications.py`, `test_render_text.py`, `test_render_web_data.py` | reworked/extended |
| `CLAUDE.md` | add `scripts/publications.py` to Layout; confirm phasing table unchanged (maintenance item) |
