# Twin opinions overlay - design

**Date:** 2026-06-25
**Status:** Approved (brainstorm)
**Scope:** A `master-cv/` extension, not a new phase. Builds on Phase 13's overlay architecture.

## Motivation

The digital twin (Phase 12a) answers questions about Jin-Ho strictly from CV facts.
It can recite *what he did* but has no access to *what he thinks* - his technical taste, domain judgments, or working philosophy.

Inspired by the "everyone should have an OPINIONS.md" idea (Kun Chen, blog.kunchenguid.com), this adds a curated opinions layer that feeds the twin, so that when someone asks "what's your take on X", the twin can answer in Jin-Ho's actual voice with his actual views - not a hedge or a fact-recitation.

We deliberately adopt only the *file* idea, not the blog's automated machinery.
There is no cron, no public-writing sync, and no drift watchdog.
The opinions file is hand-curated, exactly like the rest of the `master-cv/` overlay.

## Decisions (from brainstorm)

1. **Home:** a dedicated overlay section, not a plain narrative file.
   Opinions are a distinct *kind* of content (judgments, not biography), so they get their own field + their own rendered section, mirroring how `timeline` / `inventory` / `narrative` are each separate.
2. **Twin behavior:** voice opinions *only when asked* an opinion-shaped question.
   Facts remain the default; the twin does not proactively editorialize.
3. **Content scope:** a focused core (field + craft + careers) plus a light, bounded "broader interests" section.

## Architecture

### Data flow (unchanged shape)

```
master-cv/opinions.md  (gitignored, real)
master-cv.example/opinions.md  (committed, synthetic template)
        │
        ▼
master_cv_loader.load_master_cv()  →  MasterCV.opinions: str | None
        │
        ▼
profile_union.full_profile()  →  "## Opinions & Technical Taste (master record)" block
        │
        ▼
render_chat_context.py  →  dist/chat-context.md  →  Worker system instruction
```

This reuses the entire Phase 13 plumbing: gitignored real file, committed synthetic example, `MASTER_CV_DIR` resolution, graceful absence, PII guard on the `master-cv/` path.

### Component changes

**`scripts/master_cv_loader.py`**
- Add `opinions: str | None` to the `MasterCV` dataclass.
- In `load_master_cv`, read `master-cv/opinions.md` if it exists; `None` when absent.
- The whole loader still returns `None` when the overlay dir is absent (unchanged).

**`scripts/profile_union.py`**
- Add a private `_opinions(master_cv)` helper rendering a `## Opinions & Technical Taste (master record)` section from the raw Markdown text (rstripped, like `_narrative`).
- In `full_profile`, append the block only when `master_cv.opinions` is truthy.
- This preserves the graceful-absence / byte-identity guarantee: no opinions ⇒ no block ⇒ output unchanged.

**`worker/src/persona.ts`**
- Add one new rule licensing gated opinion-expression. Proposed text:

  > **OPINIONS (when asked):** When a question asks for my view, take, or opinion ("what do you think about X", "how do you see Y"), and the CV CONTEXT includes a section headed *Opinions & Technical Taste*, you may share those as my genuine views - clearly as opinion, not fact, and only on topics that section covers. For non-opinion questions, stay factual and don't editorialize. Never invent opinions I haven't expressed there.

- RULE 1 (grounding) is otherwise untouched: the twin still cannot invent opinions any more than it can invent facts.

**`master-cv.example/opinions.md`** (new, committed, synthetic)
- Authoring-note block + privacy note (it rides into the **public** twin on every `just worker-deploy`).
- Sections, each with SYNTHETIC placeholder claims in a "claim + brief why" shape:
  - `## On my field (bioinformatics & data science)`
  - `## On engineering & craft`
  - `## On working & careers`
  - `## Broader interests (light)` - deliberately bounded
- Markdown prose/bullets, not YAML: it is narrative context for an LLM, same substrate the existing narrative files use.

## Testing

Mirror the existing overlay-section tests (timeline / inventory / narrative):

- **Graceful absence:** with no overlay (the conftest absent-sentinel default), chat-context output is byte-identical to CV-only. Already guaranteed; add an explicit assertion that no `Opinions & Technical Taste` heading appears.
- **Present:** with a `tmp_path` fixture overlay containing an `opinions.md`, `full_profile` emits the `## Opinions & Technical Taste (master record)` block with the file's content.
- **Loader:** `load_master_cv` populates `MasterCV.opinions` from the file and leaves it `None` when the file is absent but the dir exists.
- No test reads the real overlay (the conftest autouse fixture redirects `MASTER_CV_DIR` to an absent sentinel).

## Non-code checks (confirm, do not assume)

- **PII guard:** `opinions.md` is under the already-blocked `master-cv/` path; `check_pii.py` should need no change. Confirm by running `just check-pii` reasoning, not by inspection alone.
- **Schema:** `master-cv.schema.json` validates only the overlay YAML files; freeform `opinions.md` needs no schema change. Confirm.
- **Snapshots:** run `just snapshots-update` only if a committed fixture changes the golden output (expected: none, since the real overlay is absent in CI). Eyeball any diff.

## Docs

- Refresh the Phase 13 row / `master-cv/` convention in `CLAUDE.md` to note the opinions section.
- Add `opinions.md` to the `master-cv.example/` layout listing.
- Per standing convention, the implementation plan's final task updates `CLAUDE.md`.

## Out of scope (YAGNI)

- No cron / public-writing sync / drift watchdog (the blog's automation).
- No evidence links per opinion (those serve auto-extraction, which we skip).
- No `~/OPINIONS.md` global file or `~/VOICE.md` (separate, home-level concerns; this is the CV twin only).
- No German translation of the opinions content (the twin context is English; overlay narrative is already EN-only).
