# Twin Opinions Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a curated opinions layer to the `master-cv/` overlay so the digital twin can voice Jin-Ho's technical taste and judgments when asked an opinion-shaped question.

**Architecture:** A new `opinions.md` overlay file flows through the existing Phase 13 plumbing (`master_cv_loader` → `profile_union` → `render_chat_context` → the Worker's system instruction), rendered as its own `## Opinions & Technical Taste (master record)` section. A single gated rule in the Worker persona licenses opinion-expression only for opinion-shaped questions. Everything is graceful-absence: no `opinions.md` means byte-identical CV-only output.

**Tech Stack:** Python 3 (overlay loader + renderers, pytest), TypeScript (Cloudflare Worker persona, vitest), Markdown (the opinions content).

## Global Constraints

- **Graceful absence / byte-identity:** with no `opinions.md`, every renderer's output must be byte-identical to today. The new `MasterCV.opinions` field defaults to `None`; the section is appended only when truthy.
- **Tests never touch the real overlay.** Use `tmp_path` fixtures or `master-cv.example/`. A conftest autouse fixture already redirects `MASTER_CV_DIR` to an absent sentinel.
- **No em dash (`—`) in any new prose or string you author.** Use a plain `-` or restructure. (Pre-existing em dashes in files you edit stay untouched; do not reformat surrounding code.)
- **`opinions.md` is freeform Markdown, not YAML.** No `master-cv.schema.json` change; it is narrative LLM context, the same substrate the existing `narrative/*.md` files use.
- **Long Markdown prose: one sentence per physical line.** Applies to the spec/plan/docs and the `master-cv.example/opinions.md` prose.
- **No PII in git.** `opinions.md` lives under the already-blocked `master-cv/` path; only the synthetic `master-cv.example/opinions.md` is committed.
- **Plain commits.** One logical change per commit, no Claude attribution / co-authored-by trailers.

---

### Task 1: `MasterCV.opinions` loader field

**Files:**
- Modify: `scripts/master_cv_loader.py`
- Test: `tests/test_master_cv_loader.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `MasterCV.opinions: str | None` (default `None`) - the raw text of `master-cv/opinions.md`, or `None` when that file is absent. `load_master_cv(path) -> MasterCV | None` is unchanged in signature.

- [ ] **Step 1: Extend the loader test's `_seed` helper and assert opinions load**

In `tests/test_master_cv_loader.py`, add an `opinions.md` write to `_seed` (after the narrative block):

```python
    (dir_ / "opinions.md").write_text("# How I think\n\nI value reproducibility.\n", encoding="utf-8")
```

Then add an assertion at the end of `test_parses_present_overlay`:

```python
    assert mcv.opinions is not None
    assert "I value reproducibility." in mcv.opinions
```

And add a focused test that opinions is `None` when the file is absent but the dir exists:

```python
def test_opinions_none_when_file_absent(tmp_path):
    (tmp_path / "mcv").mkdir()
    mcv = load_master_cv(tmp_path / "mcv")
    assert mcv is not None and mcv.opinions is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_master_cv_loader.py -v`
Expected: FAIL - `test_parses_present_overlay` errors on `mcv.opinions` (AttributeError) / `test_opinions_none_when_file_absent` fails.

(Note: `test_present_dir_with_missing_files_is_tolerant` asserts equality with `MasterCV(timeline=[], inventory={}, narrative={})`; because `opinions` defaults to `None` on both sides, that test stays green - do not change it.)

- [ ] **Step 3: Add the field and load logic**

In `scripts/master_cv_loader.py`, add the field to the dataclass (after `narrative`):

```python
@dataclass(frozen=True)
class MasterCV:
    timeline: list[dict]
    inventory: dict[str, list[str]]
    narrative: dict[str, str]  # filename stem -> markdown text
    opinions: str | None = None  # raw opinions.md text; None when absent
```

In `load_master_cv`, after the narrative loop and before `return`, read the file and pass it:

```python
    opinions: str | None = None
    op = base / "opinions.md"
    if op.exists():
        opinions = op.read_text(encoding="utf-8")

    return MasterCV(
        timeline=timeline, inventory=inventory, narrative=narrative, opinions=opinions
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_master_cv_loader.py -v`
Expected: PASS (all loader tests green).

- [ ] **Step 5: Commit**

```bash
git add scripts/master_cv_loader.py tests/test_master_cv_loader.py
git commit -m "master-cv: load opinions.md into MasterCV.opinions"
```

---

### Task 2: Render the opinions section in `profile_union`

**Files:**
- Modify: `scripts/profile_union.py`
- Test: `tests/test_profile_union.py`

**Interfaces:**
- Consumes: `MasterCV.opinions: str | None` from Task 1.
- Produces: `full_profile(content, pubs, master_cv)` appends a `## Opinions & Technical Taste (master record)` block when `master_cv.opinions` is truthy; output is unchanged when it is `None`/empty.

- [ ] **Step 1: Write the failing tests**

In `tests/test_profile_union.py`, add:

```python
def test_present_opinions_appends_section():
    content, pubs = _facts()
    mcv = MasterCV(
        timeline=[],
        inventory={},
        narrative={},
        opinions="# How I think\n\nI value reproducibility above novelty.",
    )
    out = full_profile(content, pubs, mcv)
    assert "## Opinions & Technical Taste (master record)" in out
    assert "I value reproducibility above novelty." in out


def test_absent_opinions_adds_no_section():
    content, pubs = _facts()
    mcv = MasterCV(timeline=[], inventory={}, narrative={})  # opinions defaults None
    out = full_profile(content, pubs, mcv)
    assert "Opinions & Technical Taste" not in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_profile_union.py::test_present_opinions_appends_section -v`
Expected: FAIL - the `## Opinions & Technical Taste (master record)` heading is not in the output.

- [ ] **Step 3: Add the `_opinions` helper and append it**

In `scripts/profile_union.py`, add a helper alongside `_narrative`:

```python
def _opinions(master_cv: MasterCV) -> str:
    return "## Opinions & Technical Taste (master record)\n\n" + master_cv.opinions.rstrip()
```

In `full_profile`, inside the `if master_cv is not None:` block, after the narrative append:

```python
        if master_cv.opinions:
            blocks.append(_opinions(master_cv))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_profile_union.py -v`
Expected: PASS (new tests green; `test_empty_overlay_adds_no_sections` and `test_absent_overlay_is_cv_only` stay green because `opinions` defaults to `None`).

- [ ] **Step 5: Commit**

```bash
git add scripts/profile_union.py tests/test_profile_union.py
git commit -m "profile-union: render the Opinions & Technical Taste section"
```

---

### Task 3: Synthetic `master-cv.example/opinions.md` template

**Files:**
- Create: `master-cv.example/opinions.md`
- Test: `tests/test_master_cv_example.py`

**Interfaces:**
- Consumes: nothing (committed synthetic content).
- Produces: a committed template at `master-cv.example/opinions.md` that the example-overlay test asserts exists.

- [ ] **Step 1: Write the failing test**

In `tests/test_master_cv_example.py`, add:

```python
def test_example_has_opinions_file():
    assert (EXAMPLE_DIR / "opinions.md").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_master_cv_example.py::test_example_has_opinions_file -v`
Expected: FAIL - `master-cv.example/opinions.md` does not exist yet.

- [ ] **Step 3: Create the synthetic template**

Create `master-cv.example/opinions.md` with this exact content (synthetic placeholders only; one sentence per line; no em dash):

```markdown
# How I think - opinions & technical taste (synthetic template)

> **Authoring note (delete in the real file):** everything from here down to the end of the
> "Privacy note" below is guidance, not content.
> In your real `master-cv/opinions.md`, replace this block with a one-line intro of your own
> and keep only the `##` sections, filled with your real views in place of the SYNTHETIC placeholders.

These are my durable opinions and technical taste: what I believe about my field and craft, not biography.
The twin shares them only when someone asks for my view, and always framed as opinion, not fact.

**What belongs here:** durable judgments, principles, tradeoffs I keep coming back to.
**What does not:** one-off reactions, jokes, biography (that lives in the timeline and narrative), or anything you would not say publicly.

**Privacy note:** whatever you write in the real `master-cv/opinions.md` is bundled into the
public-facing digital twin on every `just worker-deploy`, so include only opinions you are
comfortable being answered publicly.

## On my field (bioinformatics & data science)

Reproducibility is a first-class deliverable, not a nice-to-have: a result you cannot rerun is a draft. SYNTHETIC placeholder.
I am skeptical of ML in biology that reports accuracy without reporting what the model fails on. SYNTHETIC placeholder.

## On engineering & craft

I optimize for long-term maintainability over short-term speed: simple, well-bounded units beat clever ones. SYNTHETIC placeholder.
Tests come first for anything non-trivial, and I fix the lint or flake I see even when it is not mine. SYNTHETIC placeholder.

## On working & careers

Moving from academia to industry is a translation problem, not a downgrade: the rigor transfers, the incentives change. SYNTHETIC placeholder.
I do my best work when I can own a problem end to end and collaborate openly around it. SYNTHETIC placeholder.

## Broader interests (light)

I think coding agents should be judged on real, messy codebases, not toy demos. SYNTHETIC placeholder.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_master_cv_example.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add master-cv.example/opinions.md tests/test_master_cv_example.py
git commit -m "master-cv.example: add synthetic opinions.md template"
```

---

### Task 4: Gated opinion rule in the Worker persona

**Files:**
- Modify: `worker/src/persona.ts`
- Test: `worker/test/eval.test.ts`

**Interfaces:**
- Consumes: the `## Opinions & Technical Taste` section now present in `chat-context.md` when the real overlay has opinions.
- Produces: a `PERSONA` string that always carries an OPINIONS rule licensing opinion-expression only for opinion-shaped questions.

- [ ] **Step 1: Write the failing test**

In `worker/test/eval.test.ts`, add a test inside the `describe("guardrail contract", ...)` block:

```typescript
  it("ships the gated-opinions rule naming the opinions section", () => {
    const { system } = assembled("anything");
    expect(system).toMatch(/OPINIONS \(only when asked\)/i);
    expect(system).toMatch(/Opinions & Technical Taste/);
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `worker/`): `npm test -- eval`
Expected: FAIL - the persona has no OPINIONS rule yet.

- [ ] **Step 3: Add the rule to the persona**

In `worker/src/persona.ts`, insert a new numbered rule after rule 5 (CITE NATURALLY) and before the closing `Refusals stay in voice…` line. Use this exact text (note: no em dash):

```
6. OPINIONS (only when asked): When a question asks for my view, take, or opinion (for example "what do you think about X", "how do you see Y") and the CV CONTEXT includes a section headed "Opinions & Technical Taste", you may share those as my genuine views: framed clearly as opinion, not fact, and only on topics that section covers. For questions that are not asking for an opinion, stay factual and don't editorialize. Never invent opinions I haven't expressed there.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `worker/`): `npm test -- eval`
Expected: PASS. Then run the full worker suite to confirm no regression:
Run (from `worker/`): `npm test`
Expected: PASS (the existing guardrail-contract assertions for grounding / no-PII / stay-in-role still match).

- [ ] **Step 5: Commit**

```bash
git add worker/src/persona.ts worker/test/eval.test.ts
git commit -m "worker: gated persona rule to voice opinions when asked"
```

---

### Task 5: Docs, verification, and full green

**Files:**
- Modify: `CLAUDE.md`
- (Verify only) `scripts/check_pii.py` behavior, golden snapshots.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: an up-to-date `CLAUDE.md` and a confirmed-green tree (validate + test + lint + worker tests + PII guard).

- [ ] **Step 1: Update the `master-cv/` overlay convention in `CLAUDE.md`**

In the `master-cv/` convention bullet (the "**`master-cv/` is a gitignored superset overlay (Phase 13).**" paragraph), update the file list to include opinions. Change:

```
life-database (`timeline.yaml` + `inventory.yaml` + `narrative/*.md`) feeding the
```

to:

```
life-database (`timeline.yaml` + `inventory.yaml` + `narrative/*.md` + `opinions.md`) feeding the
```

- [ ] **Step 2: Update the Phase 13 row and Local-only files note in `CLAUDE.md`**

In the Phasing table, append to the Phase 13 row's status cell (after the existing `c46f092` text):

```
 · opinions overlay added 2026-06-25 (`master-cv/opinions.md` → `## Opinions & Technical Taste` in the twin context; gated persona rule voices them only when asked)
```

In the "Local-only files (not in git)" section, update the `master-cv/` line to list `opinions.md`:

```
- `master-cv/` — the unfiltered superset overlay (`timeline.yaml` + `inventory.yaml` + `narrative/*.md` + `opinions.md`). Gitignored; mirror the shape in `master-cv.example/`.
```

- [ ] **Step 3: Confirm the non-code checks (do not assume)**

Run the PII guard against the tree and confirm `master-cv.example/opinions.md` is allowed while real overlay paths stay blocked:

Run: `just check-pii`
Expected: `OK: no PII leaks detected`.

Confirm no schema change is needed (the example test already passed in Task 3; `master-cv.schema.json` validates only the YAML overlay files, not Markdown).

- [ ] **Step 4: Run the full suite and confirm no snapshot drift**

Run: `just validate && just test && just lint`
Expected: all green. The chat-context golden snapshot must NOT change (CI builds with the real overlay absent, so the opinions section is not in the snapshot). If `just test` reports snapshot drift, stop and investigate - it likely means a fixture leaked the example overlay; do not blindly run `just snapshots-update`.

Run (from `worker/`): `npm test`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note the master-cv opinions overlay in CLAUDE.md"
```

---

## Notes for the executor

- The real `master-cv/opinions.md` (Jin-Ho's actual opinions) is authored by the user, not by this plan. This plan ships only the plumbing + the committed synthetic template.
- After all tasks, the user can drop a real `master-cv/opinions.md`, run `just build-chat-context` to eyeball the rendered section, then `just worker-deploy` to make the twin opinion-aware. That deploy is a manual step, out of plan scope.
