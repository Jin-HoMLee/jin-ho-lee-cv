# Issue #42 — Renderer golden tests + content-integrity validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add byte-faithful syrupy snapshots of every shipped renderer artifact, per-renderer period-`end` edge unit tests (synthetic), and content-integrity checks in `validate.py` (hard-fail reversed periods; advisory implausible-date warnings).

**Architecture:** Three independent test/validator additions. Snapshots invoke each renderer's real write path → tmp → read bytes → assert against a committed single-file snapshot. Edge tests use synthetic dicts on pure functions. Validator gains a period helper (errors) + an advisory date function (warnings, exit 0). No `content/*.yaml` edits.

**Tech Stack:** pytest, syrupy (new dev dep), ruamel.yaml, the existing `scripts/render_*` + `scripts/validate.py`.

**Spec:** `docs/superpowers/specs/2026-06-01-issue-42-golden-tests-content-integrity-design.md`

---

## Files

- Create: `tests/test_snapshots.py` (Task 1)
- Modify: `pyproject.toml` (`[dependency-groups].dev` += syrupy) (Task 1)
- Modify: `justfile` (`snapshots-update` recipe) (Task 1)
- Create: `tests/__snapshots__/test_snapshots/*` (generated, committed) (Task 1)
- Modify: `scripts/render_text.py` (extract `_format_period`) (Task 2)
- Modify: `tests/test_render_text.py`, `tests/test_render_jsonresume.py`, `tests/test_render_jsonld.py` (edge tests) (Task 2)
- Modify: `scripts/validate.py` (`_validate_periods` + `date_warnings` + `main` wiring) (Task 3)
- Modify: `tests/test_validate.py` (integrity tests) (Task 3)
- Modify: `CLAUDE.md` (convention note) (Task 4)

---

### Task 1: syrupy dev dep + byte-faithful snapshot suite

**Files:** `pyproject.toml`, `tests/test_snapshots.py`, `justfile`, `tests/__snapshots__/`

- [ ] **Step 1: Add syrupy dev dependency**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
uv add --dev syrupy
uv run python -c "import syrupy; print('syrupy', syrupy.__version__)"
```
Expected: prints a 4.x version; `pyproject.toml` `[dependency-groups].dev` now lists `syrupy`.

- [ ] **Step 2: Write the snapshot suite**

Create `tests/test_snapshots.py`:
```python
"""Byte-faithful golden snapshots of every shipped renderer artifact.

Each test invokes the renderer's real write path and snapshots the exact bytes,
so a silent shape/byte change in resume.json / person.jsonld / cv-*.txt /
content.*.json fails CI. Regenerate intentionally with `just snapshots-update`.
"""
from __future__ import annotations

import pytest
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

from scripts import render_jsonld, render_jsonresume, render_web_data
from scripts.render_text import render as render_text


class _TextSnap(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    _file_extension = "txt"


class _JsonSnap(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    _file_extension = "json"


def test_resume_json(tmp_path, snapshot):
    out = tmp_path / "resume.json"
    render_jsonresume.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8") == snapshot.use_extension(_JsonSnap)


def test_person_jsonld(tmp_path, snapshot):
    out = tmp_path / "person.jsonld"
    render_jsonld.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8") == snapshot.use_extension(_JsonSnap)


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("target", ["bridge", "comp-bio", "ds-ml"])
def test_text_snapshot(lang, target, snapshot):
    assert render_text(lang, target) == snapshot.use_extension(_TextSnap)


@pytest.fixture(scope="module")
def web_data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("webdata")
    render_web_data.render_web_data(output_dir=d)
    return d


@pytest.mark.parametrize(
    "name",
    [
        "content.en.json",
        "content.de.json",
        "content.en.variants.json",
        "content.de.variants.json",
    ],
)
def test_web_data_snapshot(name, web_data_dir, snapshot):
    assert (web_data_dir / name).read_text(encoding="utf-8") == snapshot.use_extension(_JsonSnap)
```

- [ ] **Step 3: Run — verify it FAILS (snapshots don't exist yet)**

Run: `uv run pytest tests/test_snapshots.py -q`
Expected: every test FAILS with syrupy's "snapshot does not exist" / "snapshot not found" message (12 failures). This is the red state — no committed snapshots yet.

- [ ] **Step 4: Generate snapshots + eyeball them**

```bash
uv run pytest tests/test_snapshots.py --snapshot-update -q
ls tests/__snapshots__/test_snapshots/
```
Expected: snapshot files created (e.g. `test_resume_json.json`, `test_person_jsonld.json`, `test_text_snapshot[bridge-en].txt`, …, `test_web_data_snapshot[content.en.json].json`). Open `test_resume_json.json` and confirm it is the real JSON Resume output (sane, non-empty, no stray escaping) — these files ARE the canonical artifacts.

- [ ] **Step 5: Run — verify it PASSES**

Run: `uv run pytest tests/test_snapshots.py -q`
Expected: 12 passed.

- [ ] **Step 6: Sanity — confirm a drift turns it red**

Temporarily break one renderer to prove the snapshot guards bytes:
```bash
# append a stray space to the JSON Resume name (DON'T commit this)
python3 - <<'PY'
import pathlib, re
p = pathlib.Path("scripts/render_jsonresume.py")
s = p.read_text()
s2 = s.replace('"basics": _basics(content)', '"basics": _basics(content)  # drift-test', 1)
p.write_text(s2)
PY
uv run pytest tests/test_snapshots.py::test_resume_json -q || echo "EXPECTED: red on drift"
git checkout scripts/render_jsonresume.py   # revert the probe
```
Expected: the probe edit does NOT change output (it's a comment) → test still passes → that's a poor probe. Instead, verify by editing an actual output: change `indent=2` → `indent=3` in `render_jsonresume.main` temporarily, run `test_resume_json` (expect FAIL), then `git checkout scripts/render_jsonresume.py`. Confirm red, then revert. (The point: prove the snapshot is byte-sensitive, then restore.)

- [ ] **Step 7: Add the update recipe**

In `justfile`, after the `build-formats` recipe, add:
```make
# Regenerate committed renderer snapshots (run after an intentional output change)
snapshots-update:
    uv run pytest tests/test_snapshots.py --snapshot-update
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock tests/test_snapshots.py tests/__snapshots__ justfile
git commit -m "test: #42 add syrupy dev dep + byte-faithful renderer snapshot suite"
```

---

### Task 2: Period-`end` edge unit tests + `_format_period` helper

**Files:** `scripts/render_text.py`, `tests/test_render_text.py`, `tests/test_render_jsonresume.py`, `tests/test_render_jsonld.py`

- [ ] **Step 1: Write failing `_format_period` tests**

Append to `tests/test_render_text.py`:
```python
from scripts.render_text import _format_period


def test_format_period_dated():
    assert _format_period({"start": "2024-05", "end": "2025-07"}, "en") == "2024-05 to 2025-07"


def test_format_period_null_end_en():
    assert _format_period({"start": "2014-04", "end": None}, "en") == "2014-04 to present"


def test_format_period_absent_end_de():
    assert _format_period({"start": "2014-04"}, "de") == "2014-04 bis heute"
```

- [ ] **Step 2: Run — verify it FAILS**

Run: `uv run pytest tests/test_render_text.py -k format_period -q`
Expected: FAIL — `ImportError: cannot import name '_format_period'`.

- [ ] **Step 3: Extract `_format_period` and use it in both loops**

In `scripts/render_text.py`, add the helper above `_experience`:
```python
def _format_period(period: dict, lang: str) -> str:
    """'2024-05 to 2025-07', or '… to present' / '… bis heute' for an open end."""
    end = period.get("end") or PRESENT[lang]
    return f"{period['start']} {PERIOD_CONNECTOR[lang]} {end}"
```
In `_experience`, replace:
```python
        period_end = exp["period"].get("end") or PRESENT[lang]
        title_line = f"{exp['role']} - {exp['org']['name']}".strip()
        period_line = f"{exp['period']['start']} {PERIOD_CONNECTOR[lang]} {period_end}"
```
with:
```python
        title_line = f"{exp['role']} - {exp['org']['name']}".strip()
        period_line = _format_period(exp["period"], lang)
```
In `_selected_projects`, replace:
```python
        period_end = proj["period"].get("end") or PRESENT[lang]
        period = f"{proj['period']['start']} {PERIOD_CONNECTOR[lang]} {period_end}"
```
with:
```python
        period = _format_period(proj["period"], lang)
```

- [ ] **Step 4: Run — verify it PASSES (and no snapshot drift)**

```bash
uv run pytest tests/test_render_text.py -q
uv run pytest tests/test_snapshots.py -q
```
Expected: text tests pass; snapshots still pass (the refactor is behavior-preserving — `cv-*.txt` bytes unchanged). If a text snapshot drifts, the refactor changed output — fix the helper, do NOT `--snapshot-update`.

- [ ] **Step 5: Add JSON Resume + JSON-LD edge characterization tests**

These lock existing correct behavior (they should pass on first run; a failure means a real bug). Append to `tests/test_render_jsonresume.py`:
```python
from scripts.render_jsonresume import _work, _pad_end


def _exp(period):
    return {"experience": [{
        "org": {"name": "Org"}, "role": "Dev", "period": period, "bullets": [],
    }]}


def test_work_dated_end_emits_enddate():
    w = _work(_exp({"start": "2024-05", "end": "2025-07"}))[0]
    assert w["startDate"] == "2024-05-01"
    assert w["endDate"] == _pad_end("2025-07")


def test_work_null_end_omits_enddate():
    w = _work(_exp({"start": "2014-04", "end": None}))[0]
    assert "endDate" not in w


def test_work_absent_end_omits_enddate():
    w = _work(_exp({"start": "2014-04"}))[0]
    assert "endDate" not in w
```
Append to `tests/test_render_jsonld.py`:
```python
from scripts.render_jsonld import _works_for


def _content(*ends):
    return {"experience": [
        {"org": {"name": f"Org{i}"}, "role": "R", "period": {"start": "2014-04", **({"end": e} if e is not False else {})}}
        for i, e in enumerate(ends)
    ]}


def test_works_for_picks_null_end_entry():
    wf = _works_for(_content("2020-01", None))
    assert wf is not None and wf["name"] == "Org1"


def test_works_for_none_when_all_dated():
    assert _works_for(_content("2020-01", "2025-07")) is None
```
(`e is False` sentinel = omit the `end` key entirely; `None` = explicit null. Confirm `_works_for`'s return shape — it returns a dict with a `name`; adjust the key asserted if the actual shape differs, but do NOT change `_works_for`.)

- [ ] **Step 6: Run — verify PASS**

Run: `uv run pytest tests/test_render_jsonresume.py tests/test_render_jsonld.py -q`
Expected: all pass (characterization of existing behavior). If `test_works_for_*` fails on shape, fix the assertion to match `_works_for`'s real return (not the function).

- [ ] **Step 7: Commit**

```bash
git add scripts/render_text.py tests/test_render_text.py tests/test_render_jsonresume.py tests/test_render_jsonld.py
git commit -m "test: #42 period-end edge-case unit tests + _format_period helper"
```

---

### Task 3: Content-integrity in `validate.py`

**Files:** `scripts/validate.py`, `tests/test_validate.py`

- [ ] **Step 1: Write failing `_validate_periods` test**

Append to `tests/test_validate.py`:
```python
from datetime import date
from scripts.validate import _validate_periods, date_warnings


def test_reversed_period_is_error(tmp_path):
    (tmp_path / "experience.yaml").write_text(
        '- id: x\n  org: {name: O}\n  role: {en: R, de: R}\n'
        '  period: {start: "2025-07", end: "2024-05"}\n  bullets: []\n'
    )
    (tmp_path / "projects").mkdir()
    errors = _validate_periods(tmp_path)
    assert len(errors) == 1
    assert "end" in str(errors[0]).lower() and "start" in str(errors[0]).lower()


def test_forward_period_is_clean(tmp_path):
    (tmp_path / "experience.yaml").write_text(
        '- id: x\n  org: {name: O}\n  role: {en: R, de: R}\n'
        '  period: {start: "2024-05", end: "2025-07"}\n  bullets: []\n'
    )
    (tmp_path / "projects").mkdir()
    assert _validate_periods(tmp_path) == []


def test_null_end_period_is_clean(tmp_path):
    (tmp_path / "experience.yaml").write_text(
        '- id: x\n  org: {name: O}\n  role: {en: R, de: R}\n'
        '  period: {start: "2024-05", end: null}\n  bullets: []\n'
    )
    (tmp_path / "projects").mkdir()
    assert _validate_periods(tmp_path) == []
```

- [ ] **Step 2: Run — verify it FAILS**

Run: `uv run pytest tests/test_validate.py -k "period" -q`
Expected: FAIL — `ImportError: cannot import name '_validate_periods'`.

- [ ] **Step 3: Implement `_validate_periods` + wire into `validate_tree`**

In `scripts/validate.py`, add (near `_validate_publications`):
```python
def _iter_periods(content_dir: Path):
    """Yield (path, period_dict) for every dated period in experience + projects."""
    exp_path = content_dir / "experience.yaml"
    if exp_path.exists():
        for entry in _load_yaml(exp_path) or []:
            period = entry.get("period") if isinstance(entry, dict) else None
            if isinstance(period, dict):
                yield exp_path, period
    for proj_path in (content_dir / "projects").glob("*.en.yaml"):
        data = _load_yaml(proj_path)
        period = data.get("period") if isinstance(data, dict) else None
        if isinstance(period, dict):
            yield proj_path, period


def _validate_periods(content_dir: Path) -> list[FileError]:
    """Hard error when a period's end precedes its start (lexicographic on 'YYYY-MM')."""
    errors: list[FileError] = []
    for path, period in _iter_periods(content_dir):
        start, end = period.get("start"), period.get("end")
        if start and end and end < start:
            errors.append(FileError(path, f"period end {end!r} precedes start {start!r}"))
    return errors
```
Then, in `validate_tree`, before `return errors`, add:
```python
    errors.extend(_validate_periods(content_dir))
```

- [ ] **Step 4: Run — verify it PASSES**

Run: `uv run pytest tests/test_validate.py -k "period" -q`
Expected: 3 passed.

- [ ] **Step 5: Write failing `date_warnings` tests**

Append to `tests/test_validate.py`:
```python
def test_date_warnings_flags_future_and_ancient(tmp_path):
    (tmp_path / "experience.yaml").write_text(
        '- id: x\n  org: {name: O}\n  role: {en: R, de: R}\n'
        '  period: {start: "2010-01", end: "2035-01"}\n  bullets: []\n'
    )
    (tmp_path / "projects").mkdir()
    warns = date_warnings(tmp_path, today=date(2026, 6, 1))
    msgs = " ".join(str(w) for w in warns)
    assert "2010-01" in msgs   # < 2014 floor
    assert "2035-01" in msgs   # > 2026 + 5


def test_date_warnings_clean_within_bounds(tmp_path):
    (tmp_path / "experience.yaml").write_text(
        '- id: x\n  org: {name: O}\n  role: {en: R, de: R}\n'
        '  period: {start: "2024-05", end: "2025-07"}\n  bullets: []\n'
    )
    (tmp_path / "projects").mkdir()
    assert date_warnings(tmp_path, today=date(2026, 6, 1)) == []
```

- [ ] **Step 6: Run — verify it FAILS**

Run: `uv run pytest tests/test_validate.py -k "date_warnings" -q`
Expected: FAIL — `ImportError: cannot import name 'date_warnings'`.

- [ ] **Step 7: Implement `date_warnings` + wire into `main`**

In `scripts/validate.py`, add `from datetime import date` at the top, and:
```python
def date_warnings(content_dir: Path, *, today: date | None = None) -> list[FileError]:
    """Advisory (non-failing) warnings for implausible period years.

    Flags any year > today.year + 5 (likely a typo) or < 2014 (predates this CV's
    earliest real activity). `today` is injectable for deterministic tests.
    """
    today = today or date.today()
    ceiling = today.year + 5
    warnings: list[FileError] = []
    for path, period in _iter_periods(content_dir):
        for ym in (period.get("start"), period.get("end")):
            if not ym:
                continue
            year = int(ym[:4])
            if year > ceiling:
                warnings.append(FileError(path, f"implausible future date {ym!r} (> {ceiling})"))
            elif year < 2014:
                warnings.append(FileError(path, f"implausibly early date {ym!r} (< 2014)"))
    return warnings
```
In `main()`, after `errors = validate_tree(...)` and before the `if errors:` block, add:
```python
    warnings = date_warnings(content_dir)
    for warn in warnings:
        print(f"WARN: {warn}", file=sys.stderr)
```
(Warnings print but never change the exit code — `main` still returns 1 only when `errors`.)

- [ ] **Step 8: Run — verify it PASSES + real tree clean**

Append to `tests/test_validate.py`:
```python
def test_real_content_has_no_integrity_errors_or_warnings(content_dir):
    assert _validate_periods(content_dir) == []
    assert date_warnings(content_dir, today=date(2026, 6, 1)) == []
```
Run: `uv run pytest tests/test_validate.py -q`
Expected: all pass — incl. the real-tree check (research 2014-04 ≥ 2014; all ends ≤ 2031).

- [ ] **Step 9: Commit**

```bash
git add scripts/validate.py tests/test_validate.py
git commit -m "feat(validate): #42 hard-fail reversed periods + advisory implausible-date warnings"
```

---

### Task 4: CLAUDE.md convention note + final gate

**Files:** `CLAUDE.md`

- [ ] **Step 1: Document the snapshot + integrity conventions**

In `CLAUDE.md` "## Commands", after the `just build-formats` line, add:
```
just snapshots-update # regenerate committed renderer golden snapshots (after intentional output changes)
```
In "## Conventions", add a bullet:
```
- **Golden snapshots.** Renderer outputs (`resume.json`, `person.jsonld`, `cv-{en,de}.txt`, web `content.*.json`) are byte-snapshotted with syrupy under `tests/__snapshots__/`. CI fails on unintended drift; regenerate intentionally with `just snapshots-update`. `validate.py` also hard-fails reversed periods and advisory-warns implausible dates.
```

- [ ] **Step 2: Full gate**

```bash
uv run just validate && uv run just test && uv run just lint
```
Expected: validate OK (+ any WARN lines, none expected), all tests pass (now incl. snapshots + edge + integrity), lint clean.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: #42 note golden-snapshot + content-integrity conventions in CLAUDE.md"
```

- [ ] **Step 4: Tick issue #42 Scope boxes**

Verify each box (snapshot tests; period-end edge tests; validate.py integrity checks; TDD + green) and tick all four via `gh issue edit 42 --body-file <file>`.

---

## Notes for the executor

- **No `content/*.yaml` edits** — tests + validator only (renderer-isolation).
- **Snapshots are real artifacts** — never hand-edit a snapshot file; regenerate via `just snapshots-update` only after an *intentional* renderer change, and eyeball the diff.
- **#44 will re-baseline the JSON-LD snapshot** — expected; that issue states "#42 covers the new shape". When #44 changes `person.jsonld`, it regenerates `test_person_jsonld.json` deliberately.
- **Atomic commits**, no Claude attribution trailers.
- **`uv run just …`** if bare `just` doesn't resolve the venv; the repo's recipes already use `uv run` internally.
