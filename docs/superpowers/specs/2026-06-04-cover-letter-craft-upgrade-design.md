# Cover-letter craft upgrade — design

**Date:** 2026-06-04
**Status:** approved (design)
**Topic:** make the cover-letter generator produce personal, non-bland letters by default
**Builds on:** Phase 11 cover-letter generator (`14c93e9`), rich-text formatting (#69, `e0a0e91`)

## Problem

The cover-letter skill produces correct, well-grounded letters, but their quality
depends entirely on the human supplying sharp specifics in the interview. The skill
itself has **no craft guidance** — `SKILL.md` step 5 ("Draft") is one sentence about
grounding, and `cover_letter_core.py` is pure plumbing that never sees prose quality.
The result reads as bland / AI-generated whenever the interview answers are thin.

A six-angle web-research workflow (run 2026-06-04; HBR/Schwartzberg, Ask a Manager/Green,
The Muse, Yale OCS, Coursera AI-tell survey, plus AI-tool and prompt-engineering surveys)
converged on one root cause and three mechanical tells:

- **Root cause:** the letter *restates the résumé* instead of doing the one job the résumé
  can't — answer "why I **want** this job" and show *how* I work.
- **Tell 1 — adjectives standing in for evidence** ("results-driven", "detail-oriented",
  "passionate"): unverifiable filler.
- **Tell 2 — the "could-be-sent-to-500-companies" property:** no concrete *this-company*
  detail. The #1 red flag recruiters cite (~67–80% say they can spot AI letters).
- **Tell 3 — uniform polish + uniform rhythm:** four tidy equal-length paragraphs, no
  contractions, em-dash tics, rule-of-three lists, "not just X but Y" molds.

Deepest insight for *this* tool: the model's default failure is **"laundering"** the
user's plain, specific words into generic corporate prose — turning *"I rewrote their
variant-calling pipeline because it kept dropping reads"* into *"I am passionate about
leveraging robust solutions."* The skill currently has zero defense against this.

## Goal

Make a strong, personal letter the **floor the skill guarantees**, not the ceiling it
occasionally reaches — while preserving every existing constraint: never fabricate
(every claim traces to the CV or an explicit interview answer), works in EN + DE,
`applications/` stays gitignored, `content/` is read-only from this flow, PII only in
the gitignored PDF.

## Architecture — three cleanly separated surfaces

| Surface | What changes | Why here |
|---|---|---|
| `reference.md` | + "How to write the body" (positive principles); + "AI tells & clichés to avoid" (human-facing list); + `joy` / `voice_sample` field docs | The drafting agent reads this; craft knowledge belongs here |
| `SKILL.md` | step 3 wires the gap report; step 4 adds hook/joy/voice-sample prompts; step 5 adds voice-priming + "every paragraph" scope + a self-critique→revise sub-step | Procedural changes (#2, #3, #4, wiring #5) |
| Python (`cover_letter_core.py`, new `scripts/letter_lint.py`, new `scripts/jd_gap.py` CLI) | `jd_keyword_gap()` (#5); `lint_body()` advisory linter (#6) | Deterministic, tested, mirrors `validate.py`'s `date_warnings` |

## The six changes

### #1 — Anti-slop drafting brief (prompt-only)

Two new `reference.md` sections (paste-ready blocks in the Appendix). `SKILL.md` step 5
gains the explicit-scope instruction: *"Apply the drafting principles and the AI-tells
list in reference.md to **every paragraph** — the model won't generalize the rule from
one paragraph to the rest."* (Phrasing per Anthropic Opus 4.8 literal-instruction guidance.)

### #2 — Voice-sample emulation (prompt-only)

`SKILL.md` step 5, before drafting: treat the raw `interview.yaml` answers + `profile.yaml`
+ `references.md` as a `<voice_sample>`: *"These are Jin-Ho's own words. Match his diction,
sentence rhythm, and formality. Reuse his actual phrasings where they fit; do not upgrade
plain, specific words into polished corporate English — that laundering is the main way
this reads as AI."*

### #3 — Self-critique → revise pass (prompt-only)

`SKILL.md` step 5, between Draft and "show the user": silently self-score the draft 1–10 on
**Directness, Rhythm, Authenticity (matches the voice sample), Specificity (every claim
CV-traceable), Density (anything cuttable?)**; rewrite any sentence pulling a dimension
below 7; re-score once; then present. The user sees the improved draft plus a one-line
"ran a self-critique pass" note — not the scores.

### #4 — Opening-hook requirement + interview prompt (prompt-only)

`reference.md` rule: open with a **Story hook** (a concrete remembered moment), an
**Achievement hook** (a specific result), or a **Research hook** (a specific, verifiable
insight about *this* company) — never "I am writing to apply"; the body must deliver on
the opening's promise. `SKILL.md` step 4 gains a sharper prompt for the specific moment /
detail / connection that drew the user to *this* company (raw material for the hook).

### #5 — Deterministic honesty diff (code)

New `cover_letter_core.jd_keyword_gap(slug) -> dict`, surfaced by **`just jd-gap <slug>`**
(thin CLI `scripts/jd_gap.py`, mirroring `scripts/render_letter.py`), run by the agent in
step 3 before drafting.

- **CV evidence vocabulary:** flatten all string leaves of `cv_facts()` (skills, project
  `technologies`, experience text) into a normalized token/phrase set.
- **JD side:** tokenize `job.md`, drop stopwords.
- **Output (advisory):** `evidenced` (CV terms present in the JD → emphasize) and `gaps`
  (JD requirement-ish terms with no CV match → *review-these*).
- **Contract — explicit in code + docs:** *a checklist, not a verdict.* It is deliberately
  tuned to over-surface; the gap list will contain false alarms (semantic near-misses such
  as "population cohorts" vs. "clinical cohorts", and generic words). The agent prunes
  false alarms and surfaces real gaps to the user via the existing per-gap decision flow.
  The high-precision signal is *absence*: a specific technical term appearing literally
  nowhere in the CV is a trustworthy "don't claim this" (anti-fabrication) flag.
- **Never blocks.** Deterministic and TDD'd (fixture CV + fixture JD → asserted buckets).

### #6 — Advisory cliché linter (code)

New pure module **`scripts/letter_lint.py`** — `lint_body(text, lang) -> list[str]`, holding
the **canonical machine blocklist** (EN-primary + a small DE set). Called from
`render_letter()` after assembly; prints `WARN: …` to stderr exactly like `validate.py`'s
`date_warnings`. **Never raises, never blocks** — false positives on legitimate domain words
("robust", "landscape") are expected and cheap. Works on hand-written drafts too.

To avoid two drifting blocklists: `letter_lint.py` is the canonical machine list;
`reference.md`'s list is human guidance (overlapping, not required identical).

## Data shape changes (small, mostly schema-free)

- **`profile.yaml` + `profile.schema.json`:** add **optional** `joy` (LangString `{en, de}`)
  — *"what you genuinely enjoy about the day-to-day work"* (distinct from `motivation` = the
  bigger why). Optional, so an existing profile keeps validating. The drift-guard
  `test_skill_documents_profile_fields` will require it documented in `reference.md`.
- **`interview.yaml`:** add a documented `voice_sample` field (schema-free — `interview.yaml`
  is not schema-validated, only gap-decisions are checked). One concrete anecdote in the
  user's own words, captured **verbatim**, doubling as the voice exemplar and a STAR source.
- **`applications.example/`:** update `profile.example.yaml` + `interview.example.yaml` to
  show both new fields.

## Testing, drift-guards, no snapshot churn

- **TDD throughout** for `jd_keyword_gap` and `lint_body` (red → green → refactor).
- **New drift-guard** extends `tests/test_cover_letter_skill_docs.py`: assert `reference.md`
  contains the new section headers (mirrors `test_reference_documents_body_markup`).
- **No snapshot churn expected** — #1–#4 are prompt text, #5 is a separate report, #6 only
  prints to stderr. None change rendered letter output. Verify `just snapshots-update`
  produces an empty diff; any movement is a bug to fix, not to accept.
- `just validate` / `just test` / `just lint` / `ruff format --check` all green before merge.

## Workflow

- **One GitHub issue** (enhancement) → `gh issue develop` branch → TDD implementation →
  **one cohesive PR** → offer `@claude review` → squash-merge after green CI.
- Final task updates **CLAUDE.md** (the cover-letter convention bullet + Phase 11 row note)
  per the standing "plans keep this file current" convention.

## Out of scope (YAGNI)

- The "highlight-a-line → reword as concise/direct" control surface (nice future idea).
- Italics / headings / nested lists in the body markup (the minimal markup stays minimal).
- Any LLM call inside the Python tools — `jd_keyword_gap` and `lint_body` stay deterministic.

## Appendix — paste-ready blocks

### A1 — `reference.md` "How to write the body"

```
## How to write the body

A résumé says why Jin-Ho is qualified. This letter does the one thing the résumé can't:
it says why he WANTS this specific job and shows how he works. Never restate a CV bullet —
if a sentence could be a résumé line verbatim, cut it or deepen it with the why behind it.

VOICE. Write in Jin-Ho's own voice, reconstructed from his interview answers and profile.yaml.
Match his diction, sentence rhythm, and level of formality. Reuse his actual phrasings where
they fit. Do NOT upgrade his plain, specific words into polished corporate English — that
laundering is the main way this reads as AI. Allow contractions. Vary sentence length: don't
let three sentences in a row land in the same length band. Warm but straightforward, not gushy —
the register technical/biotech readers expect.

OPEN WITH A HOOK, NOT A TITLE. The first 2–3 sentences must hook + establish relevance + hint
at value, using one of: a Story hook (a concrete remembered moment that explains why this work
matters to him), an Achievement hook (lead with a specific result), or a Research hook (a
specific, verifiable insight about THIS company). The body must then deliver on the opening's
promise. Never "I am writing to apply".

SHOW, DON'T TELL — EVERY CLAIM TRACES TO A CV FACT. A trait word may appear only if the same
sentence also names a number, a tool, a named project, or a named outcome from the CV or an
interview answer. Replace every evaluative adjective with the concrete fact that makes a reader
INFER it. If you can't cite a CV/interview fact for a sentence, cut it — never invent color.

ONE UNFAKEABLE COMPANY DETAIL. Weave in exactly one concrete, verifiable fact about this
company/role (a product, a paper, a recent launch, a stated value) that could not appear in any
other letter — bound to one specific thing Jin-Ho has done. This single bind defeats the
"could be sent to 500 companies" test. Don't repeat the company name more than ~twice, and
never substitute generic flattery ("I admire your mission") for a real detail.

MAP EVIDENCE TO THE JD EXPLICITLY. Don't make the reader connect dots — name the JD's own
requirement and attach Jin-Ho's proof for it. Every experience sentence should end in an
employer-benefit clause ("...which is what your X team needs to do Y").

HANDLE GAPS HONESTLY AND EARLY. If there's a pivot or a missing method, name it plainly in 1–2
sentences and pivot to the transferable strength — the cover letter is the recruiter-preferred
place to frame this. Let an anecdote earn the flattering conclusion; never assert "I exceed
your requirements".

CLOSE ON CONTRIBUTING + A CONCRETE NEXT STEP. End by naming what he'd contribute (not "work"),
and propose a specific action ("I'd welcome a short call to walk through the [named] pipeline").
Never the rote "thank you for your consideration".

LENGTH. Half a page to one page; 3–4 paragraphs (intro/close 1–3 sentences, body 3–5). Pick
only the strongest evidence — shorter, specific, and selective beats comprehensive.
```

### A2 — `reference.md` "AI tells & clichés to avoid"

```
## AI tells & clichés to avoid (advisory — backstop, not the main defense)

NEVER open with: "I am writing to apply for", "I am writing to express my interest in",
"I am excited to apply for the [role] at [company]", "Please accept this letter as",
"To Whom It May Concern", "Dear Sir or Madam".

NEVER close with: "Thank you for your consideration", "I look forward to hearing from you"
(unless naming a concrete topic), "I hope to be considered", "Please do not hesitate to contact me".

Hollow fit/confidence claims (cut entirely): "I would be a great/excellent fit",
"I am the perfect candidate", "uniquely qualified", "I am confident that", "valuable asset".

Empty résumé adjectives (replace with the evidence, never assert): results-driven,
results-oriented, detail-oriented, dynamic, proactive, motivated, hard-working, self-starter,
go-getter, team player, people person, passionate, proven track record, well-rounded,
hit the ground running, fast-paced environment, think outside the box, wheelhouse.

LLM-signature vocabulary (statistical ChatGPT fingerprints): delve, leverage, utilize, foster,
robust, seamless, pivotal, tapestry, landscape, realm, beacon, testament / "a testament to",
underscore, showcase, intricate, multifaceted, comprehensive, transformative, cutting-edge,
ever-evolving, vibrant, synergy, streamline, harness, embark, bolster, boasts, navigate the
complexities, unlock potential, elevate, spearhead.

Filler framing: "in today's fast-paced world", "in the realm of", "it is important to note",
"needless to say", "when it comes to", "at the end of the day", "that being said".

Transition-word tics (don't open consecutive paragraphs with): Furthermore, Moreover,
Additionally, Consequently, Nevertheless, Indeed, Hence, Thus.

Sentence MOLDS to avoid (these survive word-banning):
- rule-of-three / tricolon ("skills, collaboration, and leadership") used repeatedly
- "not just X, but Y" / "not only X but also Y" / "it's not X, it's Y" / "we don't do X, we do Y"
- "from X to Y" range constructions
- copula-avoidance ("serves as", "stands as", "marks a testament to" in place of "is")
- main-clause + present-participle tail ("..., revealing/highlighting/ensuring/demonstrating Z")

Punctuation/structure: cap em-dashes at ~one per letter; no four equal-length tidy paragraphs;
no contraction-free flawless register throughout.

Plain-word swaps: "use" not leverage/utilize; "look into" not delve into; "strong/reliable"
not robust; "work/field" not realm/landscape; show interest through what you did — never
announce "passionate about".
```

### A3 — New interview prompts (`SKILL.md` step 4)

- "What's the specific moment or detail that drew you to *this* company or role?" (hook + the
  one unfakeable company detail).
- "Tell me, in your own words, about one concrete moment from the experience you most want to
  emphasize — problem, what you actually did, how it turned out." Capture **verbatim** into
  `interview.yaml: voice_sample` (it's the voice exemplar — don't paraphrase).
- "If you were telling a smart friend over coffee why you want this job, what would you say?"
- "What do you genuinely enjoy about this kind of work — not what you're good at, what you
  actually like?" → write to `profile.yaml: joy` (evergreen; ask once).
- (Optional) "Anything in your path you'd want to get ahead of — a gap, a pivot, a non-obvious
  jump?"

## Honest assessment of the current Arrowhead draft (for reference)

The existing letter is already above the slop bar — strong hook, one unfakeable company detail
(plozasiran/REDEMPLO), show-don't-tell with numbers, textbook honest gap-handling, and a
standout human line ("took me for a postdoc before realizing I was still a master's student").
The risk is that this quality is **not guaranteed by the skill**; it depends on good interview
answers. The upgrades make it the floor. Specific sharpenings the new guidance would catch:
"concrete/exactly" used 5×; paragraph 4 is the most résumé-like; the close is a soft
rule-of-three; "uniquely compelling" / "proven ability" are mild tells.
