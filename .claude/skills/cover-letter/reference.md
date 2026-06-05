# Cover letter reference — files, fields, conventions

## Just recipes
| Recipe | Does |
|---|---|
| `just letter <slug>` | Validate-first, then render PDF + text into `applications/<slug>/` (PDF skips if Typst is absent). |
| `just jd-gap <slug>` | Advisory JD↔CV keyword report (checklist, not a verdict — over-surfaces; prune false alarms). |
| `just validate` | Validate the CV content tree (grounding source). |

## Folder layout (all under gitignored `applications/`)
- `profile.yaml` — evergreen answers, reused across every application.
- `<slug>/job.md` — the pasted job description.
- `<slug>/application.yaml` — per-job metadata (fields below).
- `<slug>/interview.yaml` — per-job answers + gap decisions.
- `<slug>/draft.md` — editable letter body (the working step).
- `<slug>/cover-letter-<lang>.pdf` / `.txt` / `-body.txt` — rendered output.

Copy shapes from the committed `applications.example/` folder.

## `application.yaml` fields
| Field | Meaning |
|---|---|
| `company` | Employer name. |
| `role` | Position title. |
| `language` | Letter language: `en` or `de` (defaults to JD language). |
| `date` | Letter date, ISO `YYYY-MM-DD`. |
| `recipient` | Optional address block: `name`, `company`, `address`. |
| `subject` | Betreff / subject line (bold in the PDF). |
| `source` | Where the job was found (e.g. LinkedIn). |
| `url` | Job posting URL. |
| `status` | `draft` / `sent` / `interview` / `rejected` / `offer`. |

## `profile.yaml` fields (evergreen)
| Field | Meaning |
|---|---|
| `motivation` | Why this field / what drives you (`{ en, de }`). |
| `work_style` | How you work (`{ en, de }`). |
| `availability` | Notice period / earliest start. |
| `salary_expectation` | Range — **context only**, never rendered unless the JD asks + user confirms. |
| `relocation` | Willingness / constraints. |
| `preferences` | Company size, remote, domain (`{ en, de }`). |
| `joy` | What you genuinely enjoy about the day-to-day work (`{ en, de }`) — distinct from `motivation` (the bigger why). |

## `interview.yaml` fields (per job)
- `why_company` — why this company/role.
- `emphasis` — CV project ids or free text to foreground.
- `gaps` — list of `{ requirement, decision, note }`; `decision` ∈
  `transferable` / `omit` / `example`.
- `notes` — extra context for the draft.
- `voice_sample` — one concrete anecdote in the user's own words, captured
  **verbatim** (problem → what they did → outcome). The voice exemplar for drafting
  and a STAR source. Optional; schema-free.

## Letter conventions
- **DIN 5008 (de):** sender letterhead, right-aligned date, recipient block, bold
  Betreff, salutation (`Sehr geehrte Damen und Herren,` or `Sehr geehrte/r <name>,`),
  body, `Mit freundlichen Grüßen`, typed name.
- **English:** same structure; salutation `Dear Hiring Manager,` / `Dear <name>,`,
  closing `Sincerely,`.
- The salutation and closing are added deterministically at render time — `draft.md`
  holds only the body paragraphs.

## Body formatting in `draft.md` (optional)
`draft.md` is plain paragraphs separated by blank lines. Two light markups are
supported — both **optional**; a draft using neither renders exactly as before:
- `**bold**` — inline bold. Rendered bold-black in the PDF, **stripped** in the text
  flavors. Use sparingly (~3 anchor phrases per letter — restraint keeps it professional).
- A blank-line-separated block whose lines **all** start with `- ` (or `* `) becomes a
  **bullet list** — accent-`•` markers in the PDF, `• ` items in the text flavors.

Parsing lives in `scripts/cover_letter_core.py` (one place, so PDF and text never
diverge). Intentionally minimal: no nesting, italics, links, or headings. The subject
line is always rendered in accent + bold with a thin rule beneath (no markup needed).

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
