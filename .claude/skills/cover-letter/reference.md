# Cover letter reference — files, fields, conventions

## Just recipes
| Recipe | Does |
|---|---|
| `just letter <slug>` | Validate-first, then render PDF + text into `applications/<slug>/` (PDF skips if Typst is absent). |
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
