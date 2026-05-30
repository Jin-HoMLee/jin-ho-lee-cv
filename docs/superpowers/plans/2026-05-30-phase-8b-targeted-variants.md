# Phase 8b — Targeted CV Variants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From the single content source, build a CV positioned for a chosen target market (`bridge` | `comp-bio` | `ds-ml`) — e.g. `just build-target comp-bio` → `dist/cv-en-comp-bio.pdf`.

**Architecture:** A new `target` axis sits orthogonal to the existing `lang` axis, resolved once inside `content_loader.load_content` *before* langstring resolution. A target variant overrides only positioning fields (headline, tagline, lead paragraph, featured-project order); `bridge` is the strict canonical fallback. Because the loader strips all variant structure and returns the same flat tree it returns today, every downstream renderer is unchanged. PDF + plain-text gain `--target`; JSON Resume, JSON-LD, and the entire web layer stay canonical `bridge`.

**Tech Stack:** Python 3.12, `ruamel.yaml`, `jsonschema` (Draft 2020-12), pytest, `uv`, `just`, Typst, GitHub Actions.

**Spec:** [`docs/superpowers/specs/2026-05-30-phase-8b-targeted-variants-design.md`](../specs/2026-05-30-phase-8b-targeted-variants-design.md)

---

## File Structure

**Modified:**
- `scripts/content_loader.py` — add `target` param + variant-resolution helpers; selected_projects becomes target-keyed.
- `schema/cv.schema.json` — add `variants` to `personal` + `profile`; `selected_projects` array → target-keyed object; new `ProjectOrder` `$def`.
- `scripts/validate.py` — selected_projects cross-ref over all target lists; profile EN/DE variant parity; headline-variant `en`+`de` completeness.
- `content/personal.yaml` — `variants` block with per-target `headline`.
- `content/profile.en.yaml`, `content/profile.de.yaml` — `variants` block with per-target `tagline` + `lead_paragraph`.
- `content/selected_projects.yaml` — flat list → `{bridge, comp-bio, ds-ml}` ordered lists.
- `pdf/build.py` — `--target` flag, thread through `prepare_data`, target-aware output filename.
- `scripts/render_text.py` — `--target` flag, thread through `render`, target-aware output filename.
- `justfile` — `build-target`, `build-targets`, `build-text-target` recipes.
- `.github/workflows/ci.yml` — PDF matrix gains `target`; artifact + release wiring.
- `CLAUDE.md` — phasing-table row for 8b.

**Created:**
- `tests/test_variants.py` — unit + integration tests for the target axis.

**Untouched (verify in review):** `scripts/langstring.py`, all `pdf/templates/*.typ`, `scripts/render_jsonresume.py`, `scripts/render_jsonld.py`, `scripts/render_web_data.py`, the entire `web/` tree.

---

## Conventions for every task

- Repo uses `uv`. Run tests with `uv run pytest ...`, validate with `uv run python -m scripts.validate`, lint with `uv run ruff check .`.
- Plain commit messages, **no** Claude attribution / co-authored-by trailers.
- After each task: `uv run python -m scripts.validate && uv run pytest -q && uv run ruff check .` must be green before committing.

---

## Task 1: Loader — `target` param + positioning-variant resolution (personal + profile)

Backward-compatible: with no `variants` key in the real YAML, the helpers are no-ops, so existing content/tests/renderers stay green. `selected_projects` is **not** touched here (Task 2).

**Files:**
- Modify: `scripts/content_loader.py`
- Create: `tests/test_variants.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_variants.py`:

```python
"""Tests for the Phase 8b target axis (bridge | comp-bio | ds-ml)."""
from __future__ import annotations

import pytest

from scripts.content_loader import (
    _resolve_personal_target,
    _resolve_profile_target,
    load_content,
)


def test_resolve_profile_target_overrides_tagline_and_lead_keeps_rest():
    profile = {
        "tagline": "BRIDGE tagline",
        "paragraphs": ["BRIDGE lead", "SHARED second"],
        "variants": {
            "comp-bio": {"tagline": "CB tagline", "lead_paragraph": "CB lead"},
        },
    }
    out = _resolve_profile_target(profile, "comp-bio")
    assert out["tagline"] == "CB tagline"
    assert out["paragraphs"] == ["CB lead", "SHARED second"]
    assert "variants" not in out


def test_resolve_profile_target_bridge_is_noop_but_strips_variants():
    profile = {
        "tagline": "BRIDGE tagline",
        "paragraphs": ["BRIDGE lead", "SHARED second"],
        "variants": {"comp-bio": {"tagline": "CB tagline"}},
    }
    out = _resolve_profile_target(profile, "bridge")
    assert out["tagline"] == "BRIDGE tagline"
    assert out["paragraphs"] == ["BRIDGE lead", "SHARED second"]
    assert "variants" not in out


def test_resolve_profile_target_partial_override_inherits_bridge_tagline():
    profile = {
        "tagline": "BRIDGE tagline",
        "paragraphs": ["BRIDGE lead", "SHARED second"],
        "variants": {"ds-ml": {"lead_paragraph": "DS lead"}},
    }
    out = _resolve_profile_target(profile, "ds-ml")
    assert out["tagline"] == "BRIDGE tagline"  # not overridden → inherited
    assert out["paragraphs"] == ["DS lead", "SHARED second"]


def test_resolve_personal_target_replaces_headline():
    personal = {
        "headline": {"en": "BRIDGE", "de": "BRIDGE-DE"},
        "email": "x@y.z",
        "variants": {"comp-bio": {"headline": {"en": "CB", "de": "CB-DE"}}},
    }
    out = _resolve_personal_target(personal, "comp-bio")
    assert out["headline"] == {"en": "CB", "de": "CB-DE"}
    assert out["email"] == "x@y.z"
    assert "variants" not in out


def test_load_content_rejects_unknown_target(content_dir):
    with pytest.raises(ValueError, match="unknown target"):
        load_content(content_dir, target="nope")


def test_load_content_strips_variants_key_from_personal_and_profile(content_dir):
    content = load_content(content_dir, lang="en", target="bridge")
    assert "variants" not in content["personal"]
    assert "variants" not in content["profile"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_variants.py -v`
Expected: FAIL — `ImportError` for `_resolve_personal_target` / `_resolve_profile_target` (not yet defined).

- [ ] **Step 3: Implement the helpers + target param in `scripts/content_loader.py`**

Add, after the `deep_merge` function (around line 24):

```python
TARGETS = ("bridge", "comp-bio", "ds-ml")


def _resolve_personal_target(personal: dict, target: str) -> dict:
    """Apply the personal positioning variant for `target`; strip 'variants'.

    Bridge — or any target without an entry — returns the base personal with the
    'variants' key removed. A variant's `headline` ({en,de} map) replaces the base.
    """
    result = copy.deepcopy(personal)
    variants = result.pop("variants", {})
    if target != "bridge" and target in variants:
        result = deep_merge(result, variants[target])
    return result


def _resolve_profile_target(profile: dict, target: str) -> dict:
    """Apply the profile positioning variant for `target`; strip 'variants'.

    A variant may override `tagline` and/or `lead_paragraph`. `lead_paragraph`
    replaces paragraphs[0]; the remaining paragraphs are inherited from bridge.
    """
    result = copy.deepcopy(profile)
    variants = result.pop("variants", {})
    override = variants.get(target, {}) if target != "bridge" else {}
    if "tagline" in override:
        result["tagline"] = override["tagline"]
    if "lead_paragraph" in override:
        result["paragraphs"] = [override["lead_paragraph"], *result["paragraphs"][1:]]
    return result
```

Change the `load_content` signature (lines 49–54) to add `target`:

```python
def load_content(
    content_dir: Path,
    *,
    private_path: Path | None = None,
    lang: str = "en",
    target: str = "bridge",
) -> dict[str, Any]:
```

At the very top of `load_content`'s body (before loading `personal.yaml`), add the guard:

```python
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; expected one of {TARGETS}")
```

After the personal + private-overlay block (currently ends at line 67 `personal = deep_merge(...)`), add:

```python
    personal = _resolve_personal_target(personal, target)
```

> Order note: the private overlay only carries `phone`/`address`, never `headline`/`variants`, so resolving the target after the private merge is safe today. If private data ever overlaps positioning fields, resolve the target variant first.

Replace the profile load in the `content` dict (line 80) so it is target-resolved. Change:

```python
        "profile": _load_yaml(content_dir / f"profile.{lang}.yaml"),
```

to:

```python
        "profile": _resolve_profile_target(
            _load_yaml(content_dir / f"profile.{lang}.yaml"), target
        ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_variants.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the full gate**

Run: `uv run python -m scripts.validate && uv run pytest -q && uv run ruff check .`
Expected: all green (real content has no `variants` yet; helpers are no-ops on it).

- [ ] **Step 6: Commit**

```bash
git add scripts/content_loader.py tests/test_variants.py
git commit -m "feat(loader): add target axis with bridge fallback for positioning"
```

---

## Task 2: selected_projects → target-keyed map (loader + schema + validate + content, atomic)

These four changes are coupled — the loader, schema, validator, and YAML file all describe the same shape and must land together to stay green.

**Files:**
- Modify: `scripts/content_loader.py`
- Modify: `schema/cv.schema.json`
- Modify: `scripts/validate.py`
- Modify: `content/selected_projects.yaml`
- Modify: `tests/test_variants.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_variants.py`:

```python
from scripts.content_loader import _select_project_ids


def test_select_project_ids_returns_target_order():
    m = {"bridge": ["L5", "L1"], "comp-bio": ["L1", "L2", "L5"]}
    assert _select_project_ids(m, "comp-bio") == ["L1", "L2", "L5"]


def test_select_project_ids_falls_back_to_bridge_when_target_absent():
    m = {"bridge": ["L5", "L1", "L2"]}  # no ds-ml key
    assert _select_project_ids(m, "ds-ml") == ["L5", "L1", "L2"]


def _ids(projects):
    return [p["id"] for p in projects]


def test_load_content_bridge_project_order(content_dir):
    content = load_content(content_dir, lang="en", target="bridge")
    assert _ids(content["selected_projects"]) == ["L5", "L1", "L2"]


def test_load_content_comp_bio_project_order(content_dir):
    content = load_content(content_dir, lang="en", target="comp-bio")
    assert _ids(content["selected_projects"]) == ["L1", "L2", "L5"]


def test_load_content_ds_ml_project_order(content_dir):
    content = load_content(content_dir, lang="en", target="ds-ml")
    assert _ids(content["selected_projects"]) == ["C1", "D1", "D2"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_variants.py -v`
Expected: FAIL — `ImportError` for `_select_project_ids`, and order assertions fail.

- [ ] **Step 3: Convert `content/selected_projects.yaml`**

Replace the whole file with:

```yaml
# Featured-project order per positioning target.
# Each ID must resolve to content/projects/<id>.{en,de}.yaml.
# `bridge` is required and is the fallback for any target without its own key.
bridge:   [L5, L1, L2]   # genomics-led canonical (unchanged from Phase 8a)
comp-bio: [L1, L2, L5]   # neoantigen discovery, HLA pipeline, reproducible splice workflow
ds-ml:    [C1, D1, D2]   # KYC/BigQueryML, real-time ASL ML, badminton AI
```

- [ ] **Step 4: Update the loader — `scripts/content_loader.py`**

Add this helper next to the other resolvers (after `_resolve_profile_target`):

```python
def _select_project_ids(selected_map: dict, target: str) -> list[str]:
    """Return the project-id order for `target`, falling back to the bridge order."""
    return selected_map.get(target, selected_map["bridge"])
```

Replace the selected-projects block (currently lines 70–76):

```python
    selected_ids = _load_yaml(content_dir / "selected_projects.yaml")
    unknown = [pid for pid in selected_ids if pid not in projects]
    if unknown:
        raise ValueError(
            f"selected_projects.yaml references unknown project id(s): {unknown}"
        )
    selected_projects = [projects[pid] for pid in selected_ids]
```

with:

```python
    selected_map = _load_yaml(content_dir / "selected_projects.yaml")
    selected_ids = _select_project_ids(selected_map, target)
    unknown = [pid for pid in selected_ids if pid not in projects]
    if unknown:
        raise ValueError(
            f"selected_projects.yaml references unknown project id(s): {unknown}"
        )
    selected_projects = [projects[pid] for pid in selected_ids]
```

> Invariant: `content['selected_projects']` returned by `load_content` remains a **flat list of project dicts** — the target-keyed map exists only in the YAML and is resolved to a single ordered list here. Downstream renderers iterate that list unchanged.

- [ ] **Step 5: Update the schema — `schema/cv.schema.json`**

Add a new `$def` (place it right after the `ProjectId` definition, which ends at the line with `"pattern": "^[LDC][0-9]+$"`):

```json
    "ProjectOrder": {
      "type": "array",
      "items": { "$ref": "#/$defs/ProjectId" },
      "minItems": 1
    },
```

Replace the `selected_projects` definition (currently the array at lines 200–204):

```json
    "selected_projects": {
      "type": "array",
      "items": { "$ref": "#/$defs/ProjectId" },
      "minItems": 1
    },
```

with:

```json
    "selected_projects": {
      "type": "object",
      "properties": {
        "bridge":   { "$ref": "#/$defs/ProjectOrder" },
        "comp-bio": { "$ref": "#/$defs/ProjectOrder" },
        "ds-ml":    { "$ref": "#/$defs/ProjectOrder" }
      },
      "required": ["bridge"],
      "additionalProperties": false
    },
```

- [ ] **Step 6: Update the validator — `scripts/validate.py`**

Replace the selected-projects cross-ref block (currently lines 134–145):

```python
    selected_path = content_dir / "selected_projects.yaml"
    if selected_path.exists():
        try:
            selected = _load_yaml(selected_path)
            unknown = [pid for pid in selected if pid not in project_ids]
            if unknown:
                errors.append(FileError(
                    selected_path,
                    f"references unknown project id(s): {unknown}",
                ))
        except Exception as e:
            errors.append(FileError(selected_path, str(e)))
```

with (iterate every target's list):

```python
    selected_path = content_dir / "selected_projects.yaml"
    if selected_path.exists():
        try:
            selected = _load_yaml(selected_path)
            all_ids = {pid for order in selected.values() for pid in order}
            unknown = sorted(pid for pid in all_ids if pid not in project_ids)
            if unknown:
                errors.append(FileError(
                    selected_path,
                    f"references unknown project id(s): {unknown}",
                ))
        except Exception as e:
            errors.append(FileError(selected_path, str(e)))
```

- [ ] **Step 7: Run tests + validate**

Run: `uv run pytest tests/test_variants.py -v && uv run python -m scripts.validate`
Expected: tests PASS (11 total in file); validate prints `OK: all content files validate`.

- [ ] **Step 8: Run the full gate**

Run: `uv run python -m scripts.validate && uv run pytest -q && uv run ruff check .`
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add scripts/content_loader.py schema/cv.schema.json scripts/validate.py content/selected_projects.yaml tests/test_variants.py
git commit -m "feat: target-keyed selected_projects with bridge fallback"
```

---

## Task 3: Schema + validate — positioning-variant structure & EN/DE parity

Adds the schema for `personal.variants` / `profile.variants` (both optional, backward-compatible) plus two validator rules: profile EN/DE variant-key parity, and headline-variant `en`+`de` completeness. Real content still has no variants, so every rule passes trivially until Task 4.

**Files:**
- Modify: `schema/cv.schema.json`
- Modify: `scripts/validate.py`
- Modify: `tests/test_variants.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_variants.py`:

```python
from scripts.validate import (
    _validate_headline_variant_completeness,
    _validate_profile_variant_parity,
)
from ruamel.yaml import YAML

_yaml = YAML(typ="safe")


def _write(path, data):
    with path.open("w", encoding="utf-8") as f:
        _yaml.dump(data, f)


def test_profile_variant_parity_flags_key_mismatch(tmp_path):
    _write(tmp_path / "profile.en.yaml", {
        "tagline": "t", "paragraphs": ["a", "b"],
        "variants": {"comp-bio": {"tagline": "x", "lead_paragraph": "y"}},
    })
    _write(tmp_path / "profile.de.yaml", {
        "tagline": "t", "paragraphs": ["a", "b"],
        "variants": {"comp-bio": {"tagline": "x"}},  # missing lead_paragraph
    })
    errors = _validate_profile_variant_parity(tmp_path)
    assert errors
    assert "comp-bio" in str(errors[0])


def test_profile_variant_parity_passes_when_symmetric(tmp_path):
    payload = {
        "tagline": "t", "paragraphs": ["a", "b"],
        "variants": {"ds-ml": {"tagline": "x", "lead_paragraph": "y"}},
    }
    _write(tmp_path / "profile.en.yaml", payload)
    _write(tmp_path / "profile.de.yaml", payload)
    assert _validate_profile_variant_parity(tmp_path) == []


def test_headline_variant_completeness_flags_missing_de(tmp_path):
    _write(tmp_path / "personal.yaml", {
        "headline": {"en": "B", "de": "B"},
        "variants": {"comp-bio": {"headline": {"en": "only-en"}}},
    })
    errors = _validate_headline_variant_completeness(tmp_path)
    assert errors
    assert "comp-bio" in str(errors[0])


def test_headline_variant_completeness_passes_when_bilingual(tmp_path):
    _write(tmp_path / "personal.yaml", {
        "headline": {"en": "B", "de": "B"},
        "variants": {"comp-bio": {"headline": {"en": "x", "de": "y"}}},
    })
    assert _validate_headline_variant_completeness(tmp_path) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_variants.py -k "variant_parity or variant_completeness" -v`
Expected: FAIL — `ImportError` for the two `_validate_*` functions.

- [ ] **Step 3: Update the schema — `schema/cv.schema.json`**

In the `personal` definition's `properties` object (after the `"photo": { "type": "string" }` line, before the closing `}` of `properties`), add:

```json
,
        "variants": {
          "type": "object",
          "propertyNames": { "enum": ["comp-bio", "ds-ml"] },
          "additionalProperties": {
            "type": "object",
            "properties": { "headline": { "$ref": "#/$defs/LangString" } },
            "additionalProperties": false
          }
        }
```

In the `profile` definition's `properties` object (after the `paragraphs` property, before the closing `}` of `properties`), add:

```json
,
        "variants": {
          "type": "object",
          "propertyNames": { "enum": ["comp-bio", "ds-ml"] },
          "additionalProperties": {
            "type": "object",
            "properties": {
              "tagline": { "type": "string", "minLength": 1 },
              "lead_paragraph": { "type": "string", "minLength": 1 }
            },
            "additionalProperties": false
          }
        }
```

(Both `personal` and `profile` keep `additionalProperties: false`; adding `variants` to `properties` is what permits the key.)

- [ ] **Step 4: Add the validator rules — `scripts/validate.py`**

Add two functions after `_validate_publications` (around line 116):

```python
def _validate_profile_variant_parity(content_dir: Path) -> list[FileError]:
    """profile.en.yaml and profile.de.yaml must declare the same variant targets
    with the same overridden keys (EN/DE positioning parity)."""
    en_path = content_dir / "profile.en.yaml"
    de_path = content_dir / "profile.de.yaml"
    if not (en_path.exists() and de_path.exists()):
        return []
    en = (_load_yaml(en_path).get("variants") or {})
    de = (_load_yaml(de_path).get("variants") or {})
    errors: list[FileError] = []
    for target in sorted(set(en) | set(de)):
        en_keys = set(en.get(target) or {})
        de_keys = set(de.get(target) or {})
        if en_keys != de_keys:
            errors.append(FileError(
                de_path,
                f"variant {target!r} key mismatch EN/DE: "
                f"en={sorted(en_keys)} de={sorted(de_keys)}",
            ))
    return errors


def _validate_headline_variant_completeness(content_dir: Path) -> list[FileError]:
    """Each personal headline variant must define both 'en' and 'de' (parity with
    the bilingual base headline)."""
    path = content_dir / "personal.yaml"
    if not path.exists():
        return []
    variants = (_load_yaml(path).get("variants") or {})
    errors: list[FileError] = []
    for target in sorted(variants):
        headline = (variants.get(target) or {}).get("headline")
        if headline is not None and not ({"en", "de"} <= set(headline)):
            errors.append(FileError(
                path,
                f"variant {target!r} headline must define both 'en' and 'de'",
            ))
    return errors
```

In `validate_tree`, immediately before the `errors.extend(_validate_publications(content_dir))` line (search for that exact text — the line shifts once the two functions above are inserted), add:

```python
    errors.extend(_validate_profile_variant_parity(content_dir))
    errors.extend(_validate_headline_variant_completeness(content_dir))
```

- [ ] **Step 5: Run tests + validate**

Run: `uv run pytest tests/test_variants.py -v && uv run python -m scripts.validate`
Expected: tests PASS (15 total in file); validate prints `OK` (real content has no variants → both new rules return `[]`).

- [ ] **Step 6: Run the full gate**

Run: `uv run python -m scripts.validate && uv run pytest -q && uv run ruff check .`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add schema/cv.schema.json scripts/validate.py tests/test_variants.py
git commit -m "feat(schema): allow positioning variants with EN/DE parity checks"
```

---

## Task 4: Content — comp-bio + ds-ml positioning copy (EN + DE)

Adds the actual variant copy. The schema (Task 3) and loader (Task 1) already support it. **Copy below is the proposed starting point — refine wording during execution if desired, but keep EN/DE parallel, keep every number already present in `content/`, and update the matching assertions in the same commit so the suite stays green.**

**Files:**
- Modify: `content/personal.yaml`
- Modify: `content/profile.en.yaml`
- Modify: `content/profile.de.yaml`
- Modify: `tests/test_variants.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_variants.py`:

```python
from scripts.langstring import resolve_langstrings


def _resolved(content_dir, lang, target):
    return resolve_langstrings(
        load_content(content_dir, lang=lang, target=target), lang=lang
    )


def test_comp_bio_headline_en_de(content_dir):
    en = _resolved(content_dir, "en", "comp-bio")["personal"]["headline"]
    de = _resolved(content_dir, "de", "comp-bio")["personal"]["headline"]
    assert en == "Computational Biology · Cancer Genomics"
    assert de == "Computational Biology · Krebsgenomik"


def test_ds_ml_headline_en_de(content_dir):
    en = _resolved(content_dir, "en", "ds-ml")["personal"]["headline"]
    de = _resolved(content_dir, "de", "ds-ml")["personal"]["headline"]
    assert en == "Data Science · Machine Learning"
    assert de == "Data Science · Machine Learning"


def test_comp_bio_tagline_and_lead_paragraph(content_dir):
    profile = _resolved(content_dir, "en", "comp-bio")["profile"]
    assert profile["tagline"].startswith("Bioinformatician")
    assert profile["paragraphs"][0].startswith("Bioinformatician")


def test_ds_ml_tagline_and_lead_paragraph(content_dir):
    profile = _resolved(content_dir, "en", "ds-ml")["profile"]
    assert "production ML" in profile["tagline"]
    assert profile["paragraphs"][0].startswith("Production")


def test_second_paragraph_is_shared_across_targets(content_dir):
    bridge = _resolved(content_dir, "en", "bridge")["profile"]["paragraphs"][1]
    cb = _resolved(content_dir, "en", "comp-bio")["profile"]["paragraphs"][1]
    ds = _resolved(content_dir, "en", "ds-ml")["profile"]["paragraphs"][1]
    assert bridge == cb == ds


def test_experience_is_shared_across_targets(content_dir):
    bridge = _resolved(content_dir, "en", "bridge")["experience"]
    cb = _resolved(content_dir, "en", "comp-bio")["experience"]
    assert bridge == cb
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_variants.py -k "comp_bio or ds_ml or shared" -v`
Expected: FAIL — headline/tagline assertions fail (no variants in content yet).

- [ ] **Step 3: Add headline variants to `content/personal.yaml`**

After the `photo: "assets/photo.jpg"` line, append:

```yaml
variants:
  comp-bio:
    headline:
      en: "Computational Biology · Cancer Genomics"
      de: "Computational Biology · Krebsgenomik"
  ds-ml:
    headline:
      en: "Data Science · Machine Learning"
      de: "Data Science · Machine Learning"
```

- [ ] **Step 4: Add variants to `content/profile.en.yaml`**

Append to the file:

```yaml
variants:
  comp-bio:
    tagline: "Bioinformatician with a decade in cancer genomics — HLA typing & neoantigen discovery from real-patient NGS/RNA-Seq, reproducible Snakemake pipelines, 10+ publications."
    lead_paragraph: "Bioinformatician with deep roots in cancer genomics. Engineered in-silico pipelines for HLA typing and neoantigen discovery from real-patient NGS and RNA-Seq data — packaged as reproducible Snakemake workflows — backed by 10+ peer-reviewed publications as first- and shared-first author in Cancers, Epigenetics Methods, and OBM Genetics, grounded in wet-lab training at DKFZ, NCT, FZ Jülich, KIP, and SNU."
  ds-ml:
    tagline: "Data scientist shipping production ML on GCP — BigQueryML for anti-financial-crime & KYC, 1,000+ processes migrated to cloud, on a cancer-genomics research foundation with 10+ publications."
    lead_paragraph: "Production-focused data scientist. Architected the migration of 1,000+ analytical processes to Google Cloud and shipped BigQueryML models for anti-financial-crime & KYC; coached 100+ specialists in Python, SQL & ML — built on a cancer-genomics research foundation with 10+ peer-reviewed publications."
```

- [ ] **Step 5: Add variants to `content/profile.de.yaml`**

Append to the file:

```yaml
variants:
  comp-bio:
    tagline: "Bioinformatiker mit einem Jahrzehnt in der Krebsgenomik — HLA-Typisierung & Neoantigen-Identifizierung aus echten Patienten-NGS/RNA-Seq, reproduzierbare Snakemake-Pipelines, 10+ Publikationen."
    lead_paragraph: "Bioinformatiker mit tiefen Wurzeln in der Krebsgenomik. Entwicklung von In-silico-Pipelines zur HLA-Typisierung und Neoantigen-Identifizierung aus realen Patienten-NGS- und RNA-Seq-Daten — verpackt als reproduzierbare Snakemake-Workflows —, gestützt auf 10+ peer-reviewed Publikationen als Erst- und geteilter Erstautor in Cancers, Epigenetics Methods und OBM Genetics, aufbauend auf Wet-Lab-Ausbildung an DKFZ, NCT, FZ Jülich, KIP und SNU."
  ds-ml:
    tagline: "Data Scientist mit Produktiv-ML auf GCP — BigQueryML für Geldwäscheprävention & KYC, 1.000+ Prozesse in die Cloud migriert, auf einem Forschungsfundament in der Krebsgenomik mit 10+ Publikationen."
    lead_paragraph: "Produktionsorientierter Data Scientist. Architektur der Migration von 1.000+ analytischen Prozessen in die Google Cloud und Entwicklung von BigQueryML-Modellen für Geldwäscheprävention & KYC; Schulung von 100+ Fachkräften in Python, SQL & ML — aufbauend auf einem Forschungsfundament in der Krebsgenomik mit 10+ peer-reviewed Publikationen."
```

> Note for the executor: the DE `ds-ml` lead paragraph starts with "Produktionsorientierter" — `test_ds_ml_tagline_and_lead_paragraph` only asserts the **EN** lead starts with "Production", so DE wording is free as long as EN/DE stay parallel.

- [ ] **Step 6: Run tests + validate**

Run: `uv run pytest tests/test_variants.py -v && uv run python -m scripts.validate`
Expected: tests PASS (21 total in file). validate `OK` — parity holds (both EN and DE define `comp-bio` and `ds-ml` with keys `{tagline, lead_paragraph}`; headline variants are bilingual).

- [ ] **Step 7: Run the full gate**

Run: `uv run python -m scripts.validate && uv run pytest -q && uv run ruff check .`
Expected: all green. (`tests/test_positioning.py` still passes — bridge resolution is unchanged.)

- [ ] **Step 8: Commit**

```bash
git add content/personal.yaml content/profile.en.yaml content/profile.de.yaml tests/test_variants.py
git commit -m "content: add comp-bio and ds-ml positioning variants (EN + DE)"
```

---

## Task 5: Renderers — `--target` for PDF + plain-text builds

PDF and plain-text gain `--target`; output filename gets a `-{target}` suffix except for `bridge` (kept unsuffixed so existing links/CI names don't break). Filename logic is factored into testable helpers. JSON Resume, JSON-LD, web: untouched.

**Files:**
- Modify: `pdf/build.py`
- Modify: `scripts/render_text.py`
- Modify: `justfile`
- Modify: `tests/test_variants.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_variants.py`:

```python
from pdf.build import _pdf_filename, _parse_args as _pdf_parse_args
from scripts.render_text import _txt_filename


def test_pdf_filename_bridge_is_unsuffixed():
    assert _pdf_filename("en", "bridge") == "cv-en.pdf"
    assert _pdf_filename("de", "bridge") == "cv-de.pdf"


def test_pdf_filename_variants_are_suffixed():
    assert _pdf_filename("en", "comp-bio") == "cv-en-comp-bio.pdf"
    assert _pdf_filename("de", "ds-ml") == "cv-de-ds-ml.pdf"


def test_pdf_parse_args_target_default_and_choices():
    assert _pdf_parse_args(["--lang", "en"]).target == "bridge"
    assert _pdf_parse_args(["--lang", "en", "--target", "comp-bio"]).target == "comp-bio"
    with pytest.raises(SystemExit):
        _pdf_parse_args(["--lang", "en", "--target", "nope"])


def test_txt_filename_bridge_and_variant():
    assert _txt_filename("en", "bridge") == "cv-en.txt"
    assert _txt_filename("en", "comp-bio") == "cv-en-comp-bio.txt"


def test_render_text_threads_target():
    from scripts.render_text import render
    bridge = render("en", "bridge")
    cb = render("en", "comp-bio")
    assert bridge != cb
    assert "Computational Biology · Cancer Genomics" in cb
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_variants.py -k "pdf_filename or pdf_parse_args or txt_filename or render_text" -v`
Expected: FAIL — `ImportError` for `_pdf_filename` / `_txt_filename`, and `render` takes only `lang`.

- [ ] **Step 3: Update `pdf/build.py`**

Add a helper above `prepare_data` (after `_to_serializable`, around line 59):

```python
def _pdf_filename(lang: str, target: str) -> str:
    """Output filename; bridge is unsuffixed so existing links don't break."""
    return f"cv-{lang}.pdf" if target == "bridge" else f"cv-{lang}-{target}.pdf"
```

Change `prepare_data` to accept and thread `target`:

```python
def prepare_data(
    content_dir: Path,
    *,
    private_path: Path | None,
    lang: str,
    target: str = "bridge",
) -> dict[str, Any]:
    """Load content tree, merge private overlay, resolve langstrings, return flat dict."""
    raw = load_content(content_dir, private_path=private_path, lang=lang, target=target)
    resolved = resolve_langstrings(raw, lang=lang)
    return _to_serializable(resolved)
```

In `_parse_args`, add the `--target` argument (after the `--lang` line, around line 78):

```python
    p.add_argument(
        "--target",
        default="bridge",
        choices=["bridge", "comp-bio", "ds-ml"],
        help="Positioning target (default: bridge)",
    )
```

In `main`, thread target into `prepare_data` and the output path. Change line 108:

```python
    data = prepare_data(content_dir, private_path=private_path, lang=args.lang)
```

to:

```python
    data = prepare_data(
        content_dir, private_path=private_path, lang=args.lang, target=args.target
    )
```

and change the output-path line 116:

```python
    out_path = out_dir / f"cv-{args.lang}.pdf"
```

to:

```python
    out_path = out_dir / _pdf_filename(args.lang, args.target)
```

(The Typst `--input lang=...` line is unchanged — all target differences are already baked into `data.json`; templates are not touched.)

- [ ] **Step 4: Update `scripts/render_text.py`**

Add a helper above `render` (after `_publications`, around line 137):

```python
def _txt_filename(lang: str, target: str) -> str:
    """Output filename; bridge is unsuffixed to match the PDF naming convention."""
    return f"cv-{lang}.txt" if target == "bridge" else f"cv-{lang}-{target}.txt"
```

Change `render` to accept `target` and thread it:

```python
def render(lang: str, target: str = "bridge") -> str:
    """Return the full plain-text CV for the given language and target."""
    content = resolve_langstrings(
        load_content(CONTENT_DIR, lang=lang, target=target), lang=lang
    )
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    L = SECTION_LABELS
    # ...rest of the function body is unchanged...
```

(Leave the `sections = [...]` block and `return` exactly as they are.)

In `main`, add the `--target` arg and use the filename helper. After the `--lang` argument (line 171), add:

```python
    parser.add_argument(
        "--target",
        choices=("bridge", "comp-bio", "ds-ml"),
        default="bridge",
    )
```

Replace the output + write block (lines 180–182):

```python
    output = args.output or REPO_ROOT / "dist" / f"cv-{args.lang}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(args.lang), encoding="utf-8")
```

with:

```python
    output = args.output or REPO_ROOT / "dist" / _txt_filename(args.lang, args.target)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(args.lang, args.target), encoding="utf-8")
```

- [ ] **Step 5: Update `justfile`**

After the `build-de` recipe (line 27) — keep `build` / `build-de` as the bridge builds — add:

```make
# Build a targeted PDF → dist/cv-{lang}-{target}.pdf (bridge → dist/cv-{lang}.pdf)
build-target target lang="en":
    uv run python -m pdf.build --lang {{lang}} --target {{target}}

# Build every target × lang PDF (bridge + comp-bio + ds-ml, EN + DE)
build-targets:
    uv run python -m pdf.build --lang en
    uv run python -m pdf.build --lang de
    uv run python -m pdf.build --lang en --target comp-bio
    uv run python -m pdf.build --lang de --target comp-bio
    uv run python -m pdf.build --lang en --target ds-ml
    uv run python -m pdf.build --lang de --target ds-ml
```

After the `build-text` recipe (line 48), add:

```make
# Build a targeted plain-text CV → dist/cv-{lang}-{target}.txt
build-text-target target lang="en":
    uv run python -m scripts.render_text --lang {{lang}} --target {{target}}
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_variants.py -v`
Expected: all PASS (26 total in file).

- [ ] **Step 7: Verify the real builds locally**

Run:
```bash
uv run python -m pdf.build --lang en --target comp-bio
uv run python -m scripts.render_text --lang en --target ds-ml
```
Expected: `dist/cv-en-comp-bio.pdf` and `dist/cv-en-ds-ml.txt` exist. Open the PDF — the header shows "Computational Biology · Cancer Genomics", the lead line/paragraph are the comp-bio copy, projects lead with L1; the bridge build (`just build`) still writes `dist/cv-en.pdf` unchanged. (`dist/` is gitignored — these are local-only.)

- [ ] **Step 8: Run the full gate**

Run: `uv run python -m scripts.validate && uv run pytest -q && uv run ruff check .`
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add pdf/build.py scripts/render_text.py justfile tests/test_variants.py
git commit -m "feat(render): --target flag for PDF and plain-text builds"
```

---

## Task 6: CI — build & release the target × lang PDF matrix

The `build-pdf` job gains a `target` matrix dimension (2 → 6 jobs); artifacts and the release file list grow to all six PDFs. Bridge PDFs keep their current names. Machine formats and the web/sitemap path are unchanged. CI YAML can't be unit-tested locally — verification is the parsed-correctness of the matrix plus the locally-verified build commands from Task 5.

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Expand the `build-pdf` matrix**

Change the matrix (lines 41–43):

```yaml
    strategy:
      matrix:
        lang: [en, de]
```

to:

```yaml
    strategy:
      matrix:
        lang: [en, de]
        target: [bridge, comp-bio, ds-ml]
```

- [ ] **Step 2: Make the build step target-aware and compute the filename**

Replace the "Build … PDF" + "Upload PDF artifact" steps (lines 73–82):

```yaml
      - name: Build ${{ matrix.lang }} PDF
        run: uv run python -m pdf.build --lang ${{ matrix.lang }}

      - name: Upload PDF artifact
        uses: actions/upload-artifact@v7
        with:
          name: cv-${{ matrix.lang }}-pdf
          path: dist/cv-${{ matrix.lang }}.pdf
          retention-days: ${{ github.event_name == 'pull_request' && 30 || 1 }}
          if-no-files-found: error
```

with:

```yaml
      - name: Build ${{ matrix.lang }} / ${{ matrix.target }} PDF
        run: uv run python -m pdf.build --lang ${{ matrix.lang }} --target ${{ matrix.target }}

      - name: Compute artifact filename
        id: pdf
        run: |
          if [ "${{ matrix.target }}" = "bridge" ]; then
            echo "file=cv-${{ matrix.lang }}.pdf" >> "$GITHUB_OUTPUT"
          else
            echo "file=cv-${{ matrix.lang }}-${{ matrix.target }}.pdf" >> "$GITHUB_OUTPUT"
          fi

      - name: Upload PDF artifact
        uses: actions/upload-artifact@v7
        with:
          name: cv-${{ matrix.lang }}-${{ matrix.target }}-pdf
          path: dist/${{ steps.pdf.outputs.file }}
          retention-days: ${{ github.event_name == 'pull_request' && 30 || 1 }}
          if-no-files-found: error
```

- [ ] **Step 3: Add the six PDFs to the release file list**

In the `release` job's `Create GitHub Release` step, replace the `files:` block (lines 144–150):

```yaml
          files: |
            dist/cv-en.pdf
            dist/cv-de.pdf
            dist/resume.json
            dist/person.jsonld
            dist/cv-en.txt
            dist/cv-de.txt
```

with:

```yaml
          files: |
            dist/cv-en.pdf
            dist/cv-de.pdf
            dist/cv-en-comp-bio.pdf
            dist/cv-de-comp-bio.pdf
            dist/cv-en-ds-ml.pdf
            dist/cv-de-ds-ml.pdf
            dist/resume.json
            dist/person.jsonld
            dist/cv-en.txt
            dist/cv-de.txt
```

(The `release` job already downloads all artifacts with `merge-multiple: true` into `dist/`, so all six PDFs land there. `build-formats` is unchanged — machine formats stay bridge.)

- [ ] **Step 4: Validate the YAML parses**

Run: `uv run python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ci.yml OK')"`
Expected: `ci.yml OK` (no parse error). The six matrix jobs will run on push/PR.

> No local Python changed in this task; this YAML-parse check is the sufficient gate (the full validate+pytest+ruff gate is not applicable).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: build and release the target x lang PDF matrix"
```

---

## Task 7: Docs — phasing-table row for 8b in `CLAUDE.md`

Per repo convention, the final task updates the phasing table. The `Done`/merge-commit cell is finalized by `superpowers:finishing-a-development-branch` after the `--no-ff` merge (mirroring how 8a's final state landed in a post-merge commit).

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the 8b row**

In the Phasing table, after the `| 8a | … |` row, add:

```markdown
| 8b | Targeted CV variants (comp-bio · ds-ml from one source) | 🚧 In progress (branch `phase-8b-targeted-variants`, issue #37) |
```

> Documentation-only change; the full validate+pytest+ruff gate is not applicable.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Phase 8b row to the CLAUDE.md phasing table"
```

> At branch-finish, update this row to: `✅ Done (merged YYYY-MM-DD, PR #NN, commit MERGE_SHA)` — fill in the real merge date, PR number, and merge-commit short SHA.

---

## Task 8: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Full green gate**

Run: `uv run python -m scripts.validate && uv run pytest -q && uv run ruff check .`
Expected: validate `OK`, all tests pass, ruff clean.

- [ ] **Step 2: Build the full matrix locally**

Run: `just build-targets && just build-text-target comp-bio && just build-text-target ds-ml`
Expected: `dist/` contains `cv-en.pdf`, `cv-de.pdf`, `cv-en-comp-bio.pdf`, `cv-de-comp-bio.pdf`, `cv-en-ds-ml.pdf`, `cv-de-ds-ml.pdf`, plus the requested text variants.

- [ ] **Step 3: Confirm bridge artifacts are byte-stable**

Run:
```bash
uv run python -m scripts.render_jsonld && uv run python -m scripts.render_jsonresume
uv run python -m scripts.render_text --lang en
```
Open `dist/person.jsonld` / `dist/resume.json` / `dist/cv-en.txt` — `jobTitle`/`label` is still "Bioinformatics · Data Science", `description`/`summary` still the bridge profile. (These renderers never received `--target`; default bridge ⇒ unchanged.)

- [ ] **Step 4: Spot-check EN/DE parity on a variant**

Open `dist/cv-de-comp-bio.pdf` — header "Computational Biology · Krebsgenomik", DE comp-bio lead paragraph, projects lead with L1; second paragraph identical to the bridge DE second paragraph.

> Follow-up (out of scope for 8b, nice-to-have): an automated regression test asserting bridge-mode renderer output (`person.jsonld` / `resume.json` / `cv-en.txt`) is byte-stable. Today `tests/test_positioning.py` guards the loader-level bridge positioning — the root cause — which is sufficient for this phase; full per-renderer snapshotting is deferred.

---

## Self-Review

**1. Spec coverage** (each spec section → task):
- §4 positioning-only (4 surfaces vary, rest shared) → Tasks 1, 2, 4 + shared-content assertions (Task 4 Steps for ¶2/experience).
- §5 encoding (`base + variants`, headline/tagline/lead_paragraph/selected_projects) → Tasks 2 (selected_projects), 4 (copy); schema in Tasks 2–3.
- §6 load-time resolution, `target` default `bridge`, strip `variants`, unknown→raise → Task 1.
- §7 PDF+text vary; JSON Resume/JSON-LD/web stay bridge → Task 5 (+ Task 8 Step 3 proves machine formats unchanged).
- §8 schema + validate (target enum via `propertyNames`, base-present, EN/DE parity, cross-ref over all lists) → Tasks 2–3.
- §9 justfile + CI matrix + naming → Tasks 5–6.
- §10 illustrative copy → Task 4 (concrete copy + refine-during-execution note).
- §11 non-goals → respected (no web/`render_web_data.py`/`langstring.py`/Typst/`render_jsonresume.py`/`render_jsonld.py` edits anywhere in the plan).
- §12 DoD → Task 8 + the per-task gates.

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to". Every code step shows full code. The only deferred wording is Task 4's copy, which ships concrete strings with matching assertions and an explicit refine-in-sync instruction (mirrors 8a's spec) — not a placeholder.

**3. Type/signature consistency:** `load_content(..., target="bridge")` defined Task 1, used identically in Tasks 1/2/4/5. Helpers `_resolve_personal_target`, `_resolve_profile_target` (Task 1), `_select_project_ids` (Task 2), `_validate_profile_variant_parity` + `_validate_headline_variant_completeness` (Task 3), `_pdf_filename` (Task 5, `pdf.build`), `_txt_filename` (Task 5, `scripts.render_text`), `render(lang, target="bridge")` (Task 5) — names match every call site in the tests. `TARGETS`/CLI choices/`propertyNames` enum all use the exact strings `bridge`/`comp-bio`/`ds-ml`. Selected-projects map shape (`{bridge, comp-bio, ds-ml}` → lists) is identical across loader, schema, validator, and the YAML file.

**Greenness invariant:** every commit leaves `validate + pytest + ruff` green. The only hard-coupled change (selected_projects shape) lands atomically across loader+schema+validator+YAML in Task 2.
