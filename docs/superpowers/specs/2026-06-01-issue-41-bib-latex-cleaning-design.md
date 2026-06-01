# Issue #41 — Strip LaTeX braces & accents from publications at the data layer

**Date:** 2026-06-01
**Issue:** [#41](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/41) — `fix(bib): strip LaTeX braces & accents from publication titles in bib_loader`
**Size:** S · **Type:** bug

## Problem

`content/publications.bib` uses BibTeX protective braces and LaTeX accent macros:

- Titles: `{3D} {DNA} {FISH} …`, `{COMBO-FISH}`, `{53BP1}`, `{Ra-223}`, `@{DeutschlandCard}`, `Selection \& Implementation`
- Venues (booktitle): `Deutsche Gesellschaft f\"ur …` (ü), `Dny radia\v{c}n\'i ochrany ({DRO} 2018)` (č, í)

`scripts/bib_loader.py` normalizes only the DOI. Titles, authors, and venues pass through raw, so literal braces and backslash-accent sequences leak into **every** machine output — `dist/person.jsonld` (8×), `dist/resume.json` (6×), `dist/cv-*.txt`, and the web JSON. That directly degrades the machine-readability the architecture exists to deliver.

A `cleanTex` function already exists in `web/src/components/CodeHero.astro`, but it cleans **only the web hero** — every other renderer is unaffected, and it misses the caron (`\v{c}`) form present in the live data.

## Design

### Chokepoint

Add a private `_clean_tex(s: str) -> str` to `scripts/bib_loader.py`. Apply it in `_parse_entry` to the three derived, user-facing fields:

- `title`
- each author name (`authors` tuple)
- `venue` (the value returned by `_venue`)

`raw=dict(fields)` stays **untouched** — it remains the unprocessed source record.

Because all four Python renderers (`render_jsonld`, `render_jsonresume`, `render_text`, `render_web_data`) consume `Publication.title/.authors/.venue`, cleaning at this one point fixes every output simultaneously — the single-source payoff. The web additionally benefits everywhere titles are shown, not just the hero, since `render_web_data` now emits clean data.

### `_clean_tex` — ordered passes

Order is load-bearing: collapse braced accents → specific decodes → generic brace strip. Idempotent by construction (cleaning clean text is a no-op).

1. **Collapse braced-accent forms** (`\X{Y}` → `\XY`) so later passes catch them:
   `\"{u}`→`\"u`, `\'{e}`→`\'e`, `` \`{e} ``→`` \`e ``, `\^{o}`→`\^o`, `\~{n}`→`\~n` — regex `\\(["'`^~])\{(\w)\}` → `\\\1\2`
2. **Caron / háček** (the gap the JS misses; `\v{c}` is in the live data), braces optional:
   `\v{c}`→č `\v{C}`→Č, `\v{s}`→š `\v{S}`→Š, `\v{z}`→ž `\v{Z}`→Ž, `\v{r}`→ř `\v{R}`→Ř, `\v{e}`→ě `\v{E}`→Ě, `\v{n}`→ň `\v{N}`→Ň
3. **Umlauts + ß**: `\"a`→ä `\"o`→ö `\"u`→ü (+ uppercase), `\ss`→ß
4. **Acute / grave / circumflex / tilde / cedilla** (the existing cleanTex set):
   `\'e`→é `\'E`→É `` \`e ``→è, `\'a`→á `` \`a ``→à `\^a`→â, `\'o`→ó `\^o`→ô, `\'i`→í, `\'u`→ú, `\~n`→ñ `\~N`→Ñ, `\c{c}`→ç `\c{C}`→Ç (braces optional)
5. **LaTeX special-char escapes**: `\&`→& `\%`→% `\$`→$ `\_`→_ `\#`→# (covers `Selection \& Implementation`)
6. **Strip remaining protective braces**: remove `{` and `}` (turns `{3D} {DNA} {FISH}` → `3D DNA FISH`)

### Scope note — web `cleanTex`

Once `bib_loader` cleans upstream, `CodeHero.astro`'s `cleanTex` runs on already-clean strings → harmless idempotent no-op. The web layer is **left entirely untouched**: the issue scope is `bib_loader`, the redundant `cleanTex` is dead-but-harmless, and Pages CI runs only on `main` (no PR validation of the web build), so an unverified web edit — even a comment — carries needless risk for no functional gain. Removing `cleanTex` is recorded as an optional follow-up. (Adversarial verification confirmed the bib_loader fix additionally closes a latent leak the hero had: `CodeHero` never ran `cleanTex` over `p.authors`, so author-name accents would previously have leaked there — now cleaned at the chokepoint.)

### Fail-closed coverage guarantee

`_clean_tex` decodes a deliberately **closed set** of accent macros — the ones present in the live bib (`\"`, `\v`, `\'`, `\&`) plus a reasonable common surround. Macros outside that set (e.g. `\H{o}` Hungarian double-acute, `\u` breve) are **not** silently stripped to ASCII; they survive as a backslash sequence and are caught by the `test_real_bib_has_no_latex_residue` guard, which fails the build. This is intentional: a future contributor adding an unsupported accent gets a loud CI failure prompting a one-line map addition, rather than a silent mojibake leak. A generic lossy fallback was therefore **rejected** — it would defeat the fail-closed property.

## Testing (TDD — failing test first)

Unit tests on `_clean_tex` (fixtures drawn from the real bib):

- braces: `{3D} {DNA} {FISH}` → `3D DNA FISH`
- umlaut: `f\"ur` → `für`
- caron + acute: `radia\v{c}n\'i` → `radiační`
- braced accent: `Strahlenf\"{u}hrung`-style `\"{u}` → ü
- escape: `Selection \& Implementation` → `Selection & Implementation`
- idempotency: `clean(clean(x)) == clean(x)`

Guard test over the **live `content/publications.bib`** — the safety net:

- every parsed `title`, every author, and every non-None `venue` contains no `{`, `}`, or `\`. Any future un-decoded accent fails the build instead of leaking silently.

Existing `tests/test_bib_loader.py` cases stay green (plain titles like `T` pass through unchanged).

## Acceptance criteria (from the issue)

- [ ] Parsed publication titles contain no `{` / `}` and no backslash-accent sequences → guard test
- [ ] TDD: failing test first, then implement
- [ ] `dist/person.jsonld` and `dist/resume.json` rebuild with clean titles → verified by rebuild + grep
- [ ] `just validate && just test && just lint` green

## Out of scope

- Removing or rewriting the web `cleanTex` (left as a defensive no-op).
- Any change to BibTeX field semantics, sorting, DOI handling, or `raw`.
- Adding a LaTeX-decoding library (hand-rolled regex chosen for zero new deps + consistency with the existing web code; the guard test bounds the risk for our controlled bib).
