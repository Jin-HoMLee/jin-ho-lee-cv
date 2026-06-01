# Issue #42 — Renderer golden/snapshot tests + content-integrity validation

**Issue:** [#42](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/42) (`enhancement`, size: M)

**Goal:** Two durable safety nets — (1) byte-stable golden snapshots of every shipped renderer artifact so CI flags silent shape/byte drift, and (2) content-integrity checks in `validate.py` (hard-fail reversed periods; advisory-warn implausible dates) plus per-renderer period-`end` edge-case unit tests.

## Why

From the 2026-05-31 repo audit:
1. Renderers have schema/structure tests but **no byte-stable snapshots**, so a silent shape change in `resume.json` / `person.jsonld` / `cv-{en,de}.txt` / web `content.*.json` passes CI today. This gap is exactly what let the LaTeX-brace bug (#41) ship.
2. `validate.py` does schema + cross-ref only — it cannot catch a reversed (`end < start`) or implausible date.

## Decisions (resolved on best-practice grounds, 2026-06-01)

- **Snapshot tool: `syrupy`** (community-standard pytest snapshot plugin; first-class `--snapshot-update`; actively maintained). Snapshots are taken **byte-faithfully**: each test invokes the renderer's real write path into a `tmp_path`, reads the resulting file (or, for text, the `render()` string), and asserts it equals the stored snapshot. A custom `SingleFileSnapshotExtension` subclass stores each snapshot as a standalone file with the artifact's natural extension (`.json` / `.txt`) so committed snapshots are inspectable and diff cleanly. Snapshotting the real written bytes (not a re-serialization) guarantees the test catches the same byte-level drift the issue cares about.
- **Matrix: full** — every distinct shipped artifact (~12 snapshots). Partial coverage is how silent drift slips through.
- **Warnings: separate errors/warnings, exit 0 on warnings-only** — the standard validator contract. `validate_tree`'s existing `list[FileError]` return is **unchanged** (no caller breakage); advisory date warnings come from a new parallel function; `end < start` is a **hard** `FileError` inside `validate_tree`.
- **Date plausibility: both bounds, injectable `today`** — advisory-warn `year > today.year + 5` and `year < 2014`; `today` is injectable so tests are deterministic. (`2014` floor chosen so the real `research` start `2014-04` does not warn.)

## Scope & design

### Part 1 — Golden snapshots (`tests/test_snapshots.py`, syrupy)

**Artifacts snapshotted** (the full shipped surface; PDFs excluded — binary):

| # | Artifact | Producer | Invocation in test |
|---|---|---|---|
| 1 | `resume.json` | `render_jsonresume.main` | `main(["--output", p])` → read `p` |
| 2 | `person.jsonld` | `render_jsonld.main` | `main(["--output", p])` → read `p` |
| 3–4 | `cv-en.txt`, `cv-de.txt` (bridge) | `render_text.render` | `render(lang, "bridge")` |
| 5–8 | variant text: `cv-{en,de}` × `{comp-bio, ds-ml}` | `render_text.render` | `render(lang, target)` |
| 9–10 | `content.en.json`, `content.de.json` | `render_web_data.render_web_data` | `render_web_data(output_dir=tmp)` → read |
| 11–12 | `content.en.variants.json`, `content.de.variants.json` | `render_web_data.render_web_data` | same call, read variants files |

- Each renderer loads from the real committed `content/`, so snapshots are deterministic given fixed content. When content legitimately changes, the developer regenerates with `uv run pytest tests/test_snapshots.py --snapshot-update` (exposed as `just snapshots-update`); CI (no `--snapshot-update`) then fails on any **unintended** drift.
- Byte-faithfulness: tests 1–2 and 9–12 snapshot exactly what `main()`/`render_web_data` writes to disk (same `json.dumps(..., indent=2, ensure_ascii=False) + "\n"` path). Tests 3–8 snapshot the exact `render()` string.
- Snapshots committed under `tests/__snapshots__/test_snapshots/` (syrupy default), one file per artifact via the custom single-file extension.

### Part 2 — Period-`end` edge-case unit tests (synthetic fixtures)

The schema models a period as `{start: DateYM, end: DateYM | null}`. Ongoing roles are `end: null` **or** the key absent → rendered "present" / "heute". (The issue's "end: present" is loose wording; there is no `present` string in the schema. Current real content has only dated ends, so these paths need **synthetic** inputs.)

Three edge cases per renderer: **dated** end, **`end: null`**, **`end` absent**.

- **JSON Resume** (`tests/test_render_jsonresume.py`): feed a synthetic `content` dict (one `experience` entry per case) to `to_jsonresume`; assert `work[0].endDate` is the dated value when present and **omitted/absent** when `end` is null/missing (JSON Resume convention for current roles), and `startDate` always present.
- **JSON-LD** (`tests/test_render_jsonld.py`): same synthetic-`content` approach into `to_jsonld`; assert the work/role entity's end-date field behaves correspondingly (dated vs open-ended). Exact field follows the existing `to_jsonld` mapping (do not invent new fields — assert on whatever `_work*`/role mapping currently emits).
- **Plain text** (`tests/test_render_text.py`): extract the inline period-line formatting (`render_text.py:61-63`, `75-76`) into a small pure helper `_format_period(period: dict, lang: str) -> str` (minor, testability-driven refactor — `render()` keeps calling it, no behavior change), then unit-test it: dated → `"2024-05 – 2025-07"`; null/absent end → `"2014-04 – present"` (en) / `"… – heute"` (de). Use the existing `PRESENT`/`PERIOD_CONNECTOR` constants.

These are pure-function tests on synthetic data — independent of real content, so they never need `--snapshot-update`.

### Part 3 — Content-integrity in `validate.py`

Periods appear in `experience.yaml` (per entry) and `projects/*.yaml` (per project). Both are checked.

- **Hard-fail `end < start`** — new helper `_validate_periods(content_dir) -> list[FileError]`, appended into `validate_tree`'s aggregated errors (so it exits 1, same channel as today). String compare on `"YYYY-MM"` is correct lexicographically. Skips entries with null/absent `end` (ongoing).
- **Advisory date warnings** — new function `date_warnings(content_dir, *, today: date | None = None) -> list[FileError]` (reusing `FileError` for the message shape). For every `start`/`end` present, warn if `year > today.year + 5` or `year < 2014`. `today` defaults to `date.today()`; tests inject a fixed date.
- **`main()` wiring** — `errors = validate_tree(...)`; `warnings = date_warnings(...)`; print `WARN: <msg>` for each warning; print existing `FAIL`/`OK`; return `1` iff `errors` (warnings never fail the build). A new `--strict` flag is explicitly **out of scope** (YAGNI — easy follow-up if wanted).

Tests (`tests/test_validate.py`): synthetic period fixtures under `tests/fixtures/invalid_yaml/` (or inline `tmp_path` YAML) for `end<start` (asserts a `FileError` from `validate_tree`); `date_warnings` with an injected `today` for both future and `<2014` cases and a clean case (no warnings); a real-tree assertion that current `content/` yields **zero** integrity errors and **zero** warnings (guards against the floor/ceiling being mis-tuned against live data).

## Out of scope

- PDF snapshots (binary; ATS text-layer extraction is #47).
- `--strict` validate flag (YAGNI).
- Any `content/*.yaml` edits (renderer-isolation; this is tests + validator only).
- Refactoring renderers beyond the one small `_format_period` extraction.

## Testing / verification

- TDD throughout (write failing test → implement → green), per `CLAUDE.md`.
- `just validate && just test && just lint` green. New `syrupy` added to `[dependency-groups].dev`.
- The 12 snapshots are generated once via `--snapshot-update`, eyeballed for correctness (they ARE the real artifacts), and committed. A deliberate one-character edit to a renderer must turn the relevant snapshot test red (sanity check during execution).
- `just snapshots-update` recipe added and documented.

## Commit plan (atomic)

1. `test: #42 add syrupy dev dep + byte-faithful renderer snapshot suite` (Part 1 + recipe)
2. `test: #42 period-end edge-case unit tests + _format_period helper` (Part 2)
3. `feat(validate): #42 hard-fail reversed periods + advisory implausible-date warnings` (Part 3)
4. `docs: #42 note golden-snapshot convention in CLAUDE.md` (final — per the plans-update-CLAUDE.md rule)

(Spec doc committed first; the omitted #45 plan doc is folded into this branch as a separate housekeeping commit.)
