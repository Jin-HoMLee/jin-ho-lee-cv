---
name: cv
description: >-
  Read, edit (schema-validated), and re-render Jin-Ho Lee's codified CV. Use when
  changing content/ YAML, adding or altering a project, experience, skill, award, or
  publication, checking validation, or rebuilding machine formats.
allowed-tools: Bash(just validate), Bash(just build-formats), Bash(just test), Read, Edit
---

# Codified CV — agent guide

This repo is a machine-readable CV. **`content/` (YAML + BibTeX) is the only source of
truth.** Renderers (PDF, web, JSON Resume, JSON-LD, plain text) consume it — never edit a
renderer to change content.

## Golden rules
- Never read or write `content.private/` (phone, address — gitignored PII).
- Every content change must pass `just validate` before commit.
- Don't hand-edit generated files (`data/citations.json`, snapshots, `dist/`).

## Content model
- **Sections** (top-level under `content/`): `personal`, `profile`, `skills`, `education`,
  `experience`, `projects`, `selected_projects`, `languages`, `volunteer`, `awards`,
  `publications` (from `publications.bib`), `labels`.
- **LangStrings**: short strings are inline `{ en: "...", de: "..." }` maps; long prose lives
  in per-language files (`profile.en.yaml`/`profile.de.yaml`,
  `projects/L1.en.yaml`/`projects/L1.de.yaml`). `en` is required.
- **Variants**: positioning targets `bridge` (default), `comp-bio`, `ds-ml` under a
  `variants:` key (headline / tagline / paragraphs only).
- **Cross-refs**: `experience` bullets carry `refs: [L1, C2]` → `projects/<id>.en.yaml`.
  Every ref must resolve, and every project needs both `.en.yaml` and `.de.yaml`.

## Edit loop
1. Read the file you intend to change (e.g. `content/experience.yaml`).
2. `Edit` the YAML. Keep `{ en, de }` parity for any LangString you touch.
3. Validate — current state:
   !`just validate`
4. Rebuild machine formats: `just build-formats`
5. Eyeball the diff:
   !`git -C . diff --stat`
6. Commit (atomic, plain message, no attribution trailers).

## Error recovery
- `unknown project ref 'X'` → add `content/projects/X.en.yaml` + `X.de.yaml`, or fix the ref.
- EN/DE parity error → you edited only one language; edit the matching file too.
- Reversed-period error → `end` precedes `start` (`YYYY-MM`); fix the dates.

## Programmatic twin (MCP server)
For clients that prefer tools over shell, `scripts/mcp_server.py` exposes the same operations
over MCP (stdio): `get_cv_content`, `list_cv_files`, `validate_cv`, `propose_edit` (dry-run
diff + validation), `apply_edit` (validated write), `rerun_renderers`. Launch with
`just mcp-server`; full tool + recipe map in `reference.md`.
