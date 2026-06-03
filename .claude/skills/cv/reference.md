# CV reference — recipes & content map

## Just recipes
| Recipe | Does |
|---|---|
| `just validate` | JSON-Schema + cross-ref + bib validation (green before commit) |
| `just test` | pytest suite |
| `just lint` | ruff check |
| `just fmt` | ruff format |
| `just build-formats` | resume.json + person.jsonld + plain text + llms.txt |
| `just build` / `just build-de` | EN / DE public PDF (needs Typst) |
| `just build-targets` | all six target × lang PDFs |
| `just web-build` | static Astro site (needs pnpm) |
| `just mcp-server` | run the CV MCP server (stdio) |
| `just mcp-dev` | MCP Inspector against the server |

## Content sections
- `personal` — name, headline, email, location, links, knowsAbout, highlight_stats
- `profile` — tagline + paragraphs (per-language file)
- `skills` — categorized skill groups
- `education` — degrees / institutions
- `experience` — roles with periods, bullets, `refs`
- `projects` — per-id, per-language project deep-dives
- `selected_projects` — featured-project ordering per target
- `languages` — spoken-language proficiency
- `volunteer` — volunteering
- `awards` — title / issuer / year
- `publications` — from `publications.bib` (+ citation counts from `data/citations.json`)
- `labels` — UI section labels (LangStrings)

## Targets
`bridge` (default), `comp-bio`, `ds-ml` — positioning variants overriding headline /
tagline / profile paragraphs only.

## MCP tools
| Tool | Hint | Does |
|---|---|---|
| `get_cv_content(lang, target, section)` | read-only | load resolved content tree |
| `list_cv_files()` | read-only | list editable YAML paths |
| `validate_cv()` | read-only | validate current tree |
| `propose_edit(path, new_content)` | read-only | diff + validation, no write |
| `apply_edit(path, new_content)` | destructive | validated write |
| `rerun_renderers(which)` | — | rebuild formats / pdf / web / all |
