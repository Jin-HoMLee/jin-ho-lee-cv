# Build post: "Ask my CV" write-up + LinkedIn post (design)

Issue: #140.
Date: 2026-07-22.
Status: approved in brainstorm (venue, hook, language, AI angle, structure A all user-confirmed).

## Why

The 2026-07-21 deep-research pass found exactly one *measured* job-search payoff for a personal CV chatbot: the builder actively sharing the build (CNBC, 2026-04-30, verified 3-0).
Passive discovery (recruiters using answer engines) has no measured adoption.
This makes a build post the highest expected-ROI item in the report, at zero infrastructure cost.

## Decisions (user-confirmed)

- Shape: site write-up (long form) + short LinkedIn post linking to it.
- Hook: twin-first ("don't read my CV - ask it"), show-don't-tell, live link + example questions.
- Language: both pieces English (Phase 15 precedent; DE card links out).
- AI angle: the agent-driven build process gets a dedicated, honest section.
- Structure: demo-led narrative (approach A) with decision-log framing inside each architecture section.

## Deliverable 1: write-up at `/writeups/ask-my-cv/`

Proposed title: "Ask my CV - building a digital twin of my career from one YAML source".

### Section outline

1. **Hook.** The twin, live on the site, with 2-3 real questions the reader can paste.
2. **The twin's anatomy, as decisions.**
   Full context over RAG, and why (compiled `chat-context.md`, consensus approach under ~200k tokens).
   The free-tier model cascade (eight Gemini/Gemma rungs + a cross-vendor Workers AI fallback) and why daily caps make it necessary.
   Guardrails: persona rules, Turnstile, rate caps, and the three-surface deterministic PII guard philosophy.
   The gitignored `master-cv/` life-database overlay: the twin knows more than the CV shows, deliberately.
3. **The foundation.** One YAML+BibTeX source of truth; renderers (PDF, web, JSON Resume, JSON-LD, plain text) as interchangeable consumers; CI guards (ATS text-layer, web-guard crawler check, golden snapshots).
   Frame: the twin is just another renderer.
4. **The process, honestly.** 15 phases of brainstorm -> spec -> plan -> execute with Claude; TDD subagents; review gates; what directing agents actually looks like.
5. **Close.** Zero running cost; links: repo, twin, write-ups registry.

### Grounding rules

- Every technical claim must be true of the repo as merged on main at writing time; verify each against code, not memory.
- No invented metrics, no traffic/outcome claims, no hype adjectives.
- The CNBC framing ("sharing is the measured channel") may motivate the *post*, but the write-up itself stakes no claims about hiring outcomes.

### Web integration (Phase 15 patterns verbatim)

- New entry in the write-ups registry; warm-editorial design tokens reused.
- Crawler-safe static HTML: the full article text present without JavaScript.
- JSON-LD: `BlogPosting` (not `ScholarlyArticle` - this is a build post, not research).
- OG image, sitemap entry, DE card linking out to the EN article, bilingual cross-link.
- No interactive figures required (unlike Phase 15); if a diagram helps, it ships as static SVG with real text in the DOM.

### Guards

- Extend the `tests/test_writeup_static.py` pattern to the new page: crawler text, `BlogPosting` JSON-LD, OG tags, sitemap membership, bilingual cross-link.
- The new checks run in the `web-guard` CI job and must be proven to bite (temporarily break each assertion target once during development, per the guard-tautology lesson).

## Deliverable 2: LinkedIn post draft

- ~150-200 words, English, twin-first hook mirroring the write-up's opening; invites one question to the twin; links the write-up.
- Two variants delivered: link inline, and link-in-first-comment; Jin-Ho picks at publish time.
- The draft is committed beside the write-up source, clearly marked as the LinkedIn draft.
  It is not application material (nothing private in it), so the gitignored `applications/` convention does not apply.
- Jin-Ho reviews, edits, and personally publishes; nothing is posted by an agent.

## Voice and anti-slop

- VOICE.md is the floor: lead with the outcome, concrete, short, plain dashes (never em dash), no hype, no corporate boilerplate, honest about state.
- VOICE.md is a draft seeded from commits/chat; where it is silent, prefer plain and concrete over clever.
- The cover-letter anti-cliche standards apply to both pieces; run `scripts/letter_lint.py`'s cliche list over both drafts advisorily and fix hits.

## Acceptance criteria

- [ ] The deployed page serves the full article text in static HTML (crawler-readable), and the new web-guard checks fail when that text or the JSON-LD is removed.
- [ ] The built `web/dist` contains the registry card, OG tags, sitemap entry, and DE link-out (Pages deploys only from main, so the live-site check happens post-merge as a #140 follow-up tick).
- [ ] Every architecture claim in the article traces to a real file/behavior on main.
- [ ] The LinkedIn draft exists in both link variants, passes the advisory cliche lint with zero unaddressed hits, and reads in Jin-Ho's voice.
- [ ] Jin-Ho has approved both texts (he publishes the post himself; publishing is outside this branch).

## Out of scope

- German translation of either piece.
- Site-wide warm-editorial restyle (its own future phase).
- Any twin/Worker code change.
- Posting to LinkedIn (human-only step).
- Post-publish measurement (`/twin-insights` watch + FAQ refresh feed) - stays on issue #140 as follow-up checkboxes.

## Aftermath (tracked on #140, not in this branch)

After Jin-Ho publishes: watch `/twin-insights` for a question-volume change; feed real questions into the FAQ-refresh follow-up.
