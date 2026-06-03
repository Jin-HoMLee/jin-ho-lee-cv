# Agent Interface — thin MCP server + Claude skill over `content/` (#48)

**Date:** 2026-06-03
**Issue:** [#48](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/48) — *feat: thin MCP/agent skill over content/ + validate.py*
**Status:** Design (awaiting user review)

## 1. Goal

Make the codified CV **operable by an agent** — let an LLM read the structured content, propose edits that are hard-gated by the existing validator, and re-run the renderers — without inventing any new content model or renderer. This is the showcase "CV-as-code is agent-native" capability; it adds a *control layer* over what already exists, not new data.

Per the issue's checklist, the agent can:
- read `content/*.yaml`
- propose edits **gated by** `schema/cv.schema.json` + `scripts/validate.py`
- re-run all renderers

## 2. Decisions (settled in brainstorming)

| # | Decision | Choice |
|---|---|---|
| Form factor | skill vs MCP vs both | **Both** — a Claude Code skill (primary, human-facing) **and** a thin MCP server (programmatic twin), sharing **one Python core** so they cannot drift |
| Write model | how much the server writes | **Propose + gated apply** — read-only `propose_edit` returns a diff + validation; separate `apply_edit` validates-then-writes, marked destructive so MCP clients confirm |
| Rebuild scope | what the rebuild tool covers | `rerun_renderers(which='formats'\|'pdf'\|'web'\|'all')`, default `formats` (offline), validate-first, `pdf`/`web` degrade gracefully if Typst/pnpm absent |
| Portability | repo-local vs generic | **Repo-local** server (operates on this checkout), but the core takes `content_dir`/`schema_path` params with repo defaults — a **cheap future-public seam** (the underlying `load_content`/`validate_tree` already accept these paths, so no refactor). Generic/published product is a documented **future** direction only |

These are fixed; the rest of this spec is execution.

## 3. Architecture — one core, two thin surfaces

```
                ┌─────────────────────────────┐
                │  scripts/agent_core.py       │   pure Python, no MCP/CLI coupling
                │  read_cv · list_content_files│   reuses content_loader + validate
                │  validate_cv · propose_edit  │   + just recipes
                │  apply_edit · rerun_renderers│   all path/PII/subprocess guards live HERE
                └──────────────┬──────────────┘
            ┌──────────────────┴───────────────────┐
            ▼                                       ▼
  scripts/mcp_server.py                   .claude/skills/cv/SKILL.md
  thin FastMCP (official `mcp` SDK)        prose: teaches the agent to use its OWN
  stdio; tools map 1:1 to core             Edit + Bash(just …) following the same
  Pydantic structured output              core operations; documents the MCP server
```

**Why a shared core.** All behaviour — and crucially all the security guards — lives in `agent_core.py`, unit-testable with no MCP runtime. The MCP server is a ~mechanical wrapper. The skill is prose that drives the agent's existing tools through the *same* operations. Logic exists in exactly one place.

**Anti-drift is enforced by tests, not hope** (§8): a core↔server parity test, an MCP smoke test, and a doc drift-guard that checks every `just` recipe / schema field the skill docs mention actually exists in the *authoritative* sources (the `justfile`, `cv.schema.json`) — never by parsing prose against prose.

## 4. The core — `scripts/agent_core.py`

Module constants mirror the existing renderer convention:

```python
REPO_ROOT   = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "schema" / "cv.schema.json"
```

> **Naming note.** The repo's `render_*.py` convention is for *renderers*; non-renderer modules use descriptive nouns (`content_loader.py`, `bib_loader.py`, `validate.py`). `agent_core.py` follows that latter pattern — it is the shared foundation for the agent surfaces, not a renderer.

### 4.0 Path safety (the security spine) — `_safe_content_path`

Every edit path passes through one validator. This is the single most important function in the feature; it is the only thing standing between an external MCP client and `content.private/`.

```python
def _safe_content_path(rel_path: str, *, content_dir: Path = CONTENT_DIR) -> Path:
    """Resolve a caller-supplied content-relative path or raise ValueError.

    Rejects, in order:
      1. absolute paths            (PurePosixPath(rel_path).is_absolute() or leading '/')
      2. any '..' or '.' segment   ('..' in parts; reject dotfiles/dotdirs)
      3. non-.yaml targets         (suffix != '.yaml')  -> .bib edits are out of scope (v1)
    Then resolve symlinks and assert containment:
      4. resolved = (content_dir / rel_path).resolve()
      5. resolved must equal content_dir.resolve() child  (content_root in resolved.parents)
      6. 'content.private' must not appear in resolved.parts  (defence in depth)
    Returns the resolved absolute Path.
    """
```

Rationale for each: (1)+(2) block `../content.private/private.yaml` and multi-hop escapes; (4)+(5) `.resolve()` follows symlinks **before** the containment check, so a `content/evil.yaml → content.private/private.yaml` symlink resolves outside `content/` and is rejected; (6) is belt-and-suspenders. `.bib` is excluded because BibTeX has separate validation and the issue scopes edits to YAML; `.bib` editing is a documented future item.

### 4.1 `read_cv` — read structured content (PII-safe)

```python
def read_cv(lang: str = "en", target: str = "bridge", section: str | None = None,
            *, content_dir: Path = CONTENT_DIR) -> dict:
```

- Calls `load_content(content_dir, private_path=None, lang=lang, target=target)` — **`private_path` is hard-wired `None` and is not a parameter of `read_cv`**, so no caller (including the MCP wrapper) can request the PII overlay.
- Resolves LangStrings (`resolve_langstrings(tree, lang)`) and converts to JSON-able output by reusing the existing `render_web_data._to_jsonable` logic (Publication→dict dropping `raw`, Path→str, tuple→list). Factor that helper into `agent_core` (or import it) so both share one converter.
- `target` must be in `content_loader.TARGETS` (`bridge`/`comp-bio`/`ds-ml`), else `ValueError`.
- **Section filter.** Valid `section` values are exactly the top-level tree keys:
  `personal, profile, skills, education, experience, projects, selected_projects, languages, volunteer, awards, publications, labels`.
  `section=None` returns the whole tree; a valid section returns that sub-tree; an unknown section raises `ValueError`.

### 4.2 `list_content_files` — enumerate the editable surface

```python
def list_content_files(*, content_dir: Path = CONTENT_DIR) -> list[str]:
```

- Recursively globs `*.yaml` under `content_dir`, **resolving each result** and dropping any that escape `content_dir` or contain `content.private` (symlink-enumeration defence).
- Returns **content-relative, forward-slash, sorted** strings (e.g. `["awards.yaml", "experience.yaml", "personal.yaml", "projects/L1.en.yaml", …]`). Never absolute paths — so the existence/location of `content.private/` can never leak.
- Excludes `publications.bib` (not YAML, not v1-editable).

### 4.3 `propose_edit` — dry-run, full-tree validation, zero source mutation

```python
def propose_edit(rel_path: str, new_content: str,
                 *, content_dir: Path = CONTENT_DIR, schema_path: Path = SCHEMA_PATH) -> dict:
    # returns {"diff": str, "valid": bool, "errors": list[str], "warnings": list[str]}
```

Mechanism (precisely specified to remove implementer guesswork):
1. `dst = _safe_content_path(rel_path, content_dir=content_dir)` (raises on unsafe path).
2. With `tempfile.TemporaryDirectory()` (auto-cleanup, mode `0700`):
   - `shutil.copytree(content_dir, tmp/"content")` — **copies `content/` only; never `content.private/`**, so no PII ever enters the temp tree.
   - Write `new_content` (UTF-8) to `tmp/"content"/rel_path`.
   - `errors = validate_tree(tmp/"content", schema_path)` → list of `FileError`; `warnings = date_warnings(tmp/"content")`.
3. `diff` = `difflib.unified_diff` of the **current** file (or empty if new) vs `new_content`, 3 context lines, `fromfile`/`tofile` = `rel_path`. Empty string when unchanged.
4. Return `{diff, valid: not errors, errors: [str(e) for e in errors], warnings: [str(w) for w in warnings]}`. **No write to `content/` ever occurs.**

This validates the *whole would-be tree*, so it catches schema breaks, broken `refs`, EN/DE parity violations, reversed periods, and bib errors — byte-identical to what `just validate` (and CI) would flag. Single-file validation was rejected for missing cross-file checks.

> **`readOnlyHint` decision.** `propose_edit` writes only to a private, `0700`, auto-deleted temp dir and never mutates repo source, the working tree, or any durable/observable state, and never touches PII. We therefore mark it `readOnlyHint=True` (it is read-only with respect to the agent's environment). The temp-dir write is an implementation detail, not an environment mutation. (Alternative considered: `readOnlyHint=False` for strictness — rejected as misleading to clients that would then prompt on a pure dry-run.)

### 4.4 `apply_edit` — validate-then-write, atomic, refuses on any error

```python
def apply_edit(rel_path: str, new_content: str,
               *, content_dir: Path = CONTENT_DIR, schema_path: Path = SCHEMA_PATH) -> dict:
    # returns {"applied": bool, "errors": list[str], "warnings": list[str]}
```

1. Run `propose_edit(rel_path, new_content, …)` internally (this re-runs `_safe_content_path` and full-tree validation).
2. If `not result["valid"]` → return `{applied: False, errors, warnings}` **without writing** (rollback is trivial because nothing was written).
3. If valid → **atomic write**: write to a temp file in the *same directory* as the target, `os.replace()` onto the real file. Return `{applied: True, errors: [], warnings}`.

"Clean" therefore means **the entire tree validates** — schema + cross-refs + EN/DE parity + periods + bib. A `projects/L1.de.yaml` edit that breaks parity with `L1.en.yaml` is a `FileError` and is refused. **Multi-file atomic edits are out of scope for v1**: to add a project (needs both `.en.yaml` and `.de.yaml`), the human/agent uses the skill's `Edit` flow, not the single-file `apply_edit` tool. (Documented limitation; future item.)

> **The propose→apply split *is* the two-phase confirmation.** `propose_edit` (read-only, returns the diff) is phase 1; `apply_edit` (destructive, confirmation-gated by the MCP client via `destructiveHint`) is phase 2. We explicitly **reject** a stateful confirmation-token/expiry system (over-engineered for a single-user repo server; the MCP client's own approval prompt already gates the destructive call).

### 4.5 `rerun_renderers` — whitelisted, injection-proof, graceful

```python
def rerun_renderers(which: str = "formats",
                    *, content_dir: Path = CONTENT_DIR, schema_path: Path = SCHEMA_PATH) -> dict:
    # returns {"ran": list[str], "ok": bool, "skipped": list[str], "output": dict[str, str]}
```

- **Whitelist:** `which` must be in `{"formats", "pdf", "web", "all"}`, else `ValueError`. `which` is **never interpolated into a shell string.**
- **Recipe map** (each entry is an argv list run as `subprocess.run(["just", recipe], cwd=REPO_ROOT, capture_output=True, text=True, timeout=600)` — `shell=False` always):
  - `formats` → `build-formats`
  - `pdf` → `build`, `build-de` *(guarded by `shutil.which("typst")`)*
  - `web` → `web-build` *(guarded by `shutil.which("pnpm")`)*
  - `all` → `formats` + available `pdf` + available `web`
- **Validate-first:** call `validate_tree(content_dir, schema_path)` in-process first. If it returns errors → return `{ran: [], ok: False, skipped: [<all targets>], output: {"validate": "<errors>"}}` and run **no** recipes.
- **Graceful degradation:** if a recipe's tool is absent, add its recipe name to `skipped` and do not run it — never raise. `refresh-citations` is **never** invoked (no network; `openWorldHint=False`).
- **Return:** `ran` = recipes executed; `ok` = every executed recipe exited 0; `skipped` = recipes not attempted (missing tool); `output` = `{recipe: combined stdout+stderr}`. A skipped recipe does not make `ok` False.

### 4.6 `validate_cv` — standalone validation

```python
def validate_cv(*, content_dir: Path = CONTENT_DIR, schema_path: Path = SCHEMA_PATH) -> dict:
    # returns {"valid": bool, "errors": list[str], "warnings": list[str]}
```

Thin convenience over the existing validator on the **real** tree (read-only): `errors = validate_tree(content_dir, schema_path)`, `warnings = date_warnings(content_dir)`, return `{valid: not errors, errors: [...], warnings: [...]}`. Lets an agent check current validity without proposing an edit; backs the `validate_cv` MCP tool and the skill's "is the tree green?" step.

## 5. The MCP server — `scripts/mcp_server.py`

Thin FastMCP wrapper (**official `mcp` SDK**, `from mcp.server.fastmcp import FastMCP`). Each tool calls one core function; the **only** added logic is Pydantic response shaping and annotations.

```python
mcp = FastMCP("jin-ho-lee-cv")
# ... @mcp.tool(...) defs ...
def run() -> None:        # console-script / -m entry
    mcp.run(transport="stdio")
if __name__ == "__main__":
    run()
```

Entry point: `uv run python -m scripts.mcp_server` (works because `scripts/` is already a package with `__init__.py`). Also expose a console script `cv-mcp = "scripts.mcp_server:run"` in `pyproject.toml`.

### 5.1 Tools, names, annotations

Tool names are **snake_case** (valid per MCP `[A-Za-z0-9_.-]+`, matches the Python functions, least surprise). Every tool gets a one-line `description`.

| Tool | Core call | `readOnlyHint` | `destructiveHint` | `idempotentHint` | `openWorldHint` |
|---|---|---|---|---|---|
| `get_cv_content(lang,target,section)` | `read_cv` | **True** | false | true | **False** |
| `list_cv_files()` | `list_content_files` | **True** | false | true | **False** |
| `validate_cv()` | `validate_tree`+`date_warnings` | **True** | false | true | **False** |
| `propose_edit(path,new_content)` | `propose_edit` | **True** (§4.3) | false | true | **False** |
| `apply_edit(path,new_content)` | `apply_edit` | False | **True** | false | **False** |
| `rerun_renderers(which)` | `rerun_renderers` | False | false | true | **False** |

`get_cv_content` **hard-wires `private_path=None`** by virtue of calling `read_cv` (which has no such param) — the PII overlay is unreachable from the protocol surface.

### 5.2 Structured output (Pydantic)

Core returns plain dicts/lists; the server wraps them in Pydantic `BaseModel`s so FastMCP emits `structuredContent` (+ a JSON `TextContent` block for back-compat):
- `ProposeResult{diff:str, valid:bool, errors:list[str], warnings:list[str]}`
- `ApplyResult{applied:bool, errors:list[str], warnings:list[str]}`
- `ValidateResult{valid:bool, errors:list[str], warnings:list[str]}`
- `RenderResult{ran:list[str], ok:bool, skipped:list[str], output:dict[str,str]}`
- `get_cv_content` → `dict` (structured); `list_cv_files` → `list[str]`.

### 5.3 Dependency & client config

- `pyproject.toml`: add a dedicated group so the base pipeline stays dependency-light —
  ```toml
  [dependency-groups]
  mcp = ["mcp[cli]>=1.12"]
  ```
  (`uv sync --group mcp`; exact floor pinned during implementation via `uv.lock`.) MCP tests `pytest.importorskip("mcp")` so `just test` is green with or without the group; CI installs the group to exercise the server.
- Committed **`.mcp.json`** (Claude Code project-scoped):
  ```json
  { "mcpServers": { "jin-ho-lee-cv": {
      "command": "uv", "args": ["run", "python", "-m", "scripts.mcp_server"] } } }
  ```
  `reference.md` additionally documents the Claude Desktop `claude_desktop_config.json` form (same command with an absolute `cwd` = repo root).
- `justfile`: `mcp-server` (`uv run python -m scripts.mcp_server`) and `mcp-dev` (`uv run mcp dev scripts/mcp_server.py`, launches the MCP Inspector).

## 6. The skill — `.claude/skills/cv/`

Project-scoped, **committed** (none exists yet; we create `.claude/skills/cv/`).

`SKILL.md` frontmatter:
```yaml
---
name: cv
description: >-
  Read, edit (schema-validated), and re-render Jin-Ho Lee's codified CV. Use when
  changing content/ YAML, adding/altering a project, experience, skill, award, or
  publication, checking validation, or rebuilding machine formats.
allowed-tools: Bash(just validate), Bash(just build-formats), Bash(just test), Read, Edit
---
```

`SKILL.md` body (hand-written prose, ≤ ~300 lines):
1. **Content model cheat-sheet** — the source-of-truth principle, the section list, LangString `{en,de}` (inline vs per-language-file), the `bridge`/`comp-bio`/`ds-ml` variants, `experience.refs → projects/*` cross-links, and the **`content.private/` no-go zone**.
2. **Edit loop** — read → `Edit` the YAML → `just validate` → `just build-formats` → eyeball the golden-snapshot diff → commit. Uses inline `` !`git -C . diff --stat content/` `` / `` !`just validate` `` dynamic injection to put live state in front of the agent.
3. **Error recovery** — how to read a `FileError`, fixing EN/DE parity (edit *both* language files), reversed-period and unknown-`ref` errors.
4. **MCP server** — when/how to drive `scripts/mcp_server.py` instead (the programmatic twin), with the tool list.

`reference.md` — recipe catalog (mirrors the `justfile`) + schema/section cheat-sheet (mirrors `cv.schema.json`). Hand-written for v1, but **guarded** (§8) so it cannot silently drift from the authoritative sources. Auto-generation from schema+justfile (RenderCV's AST→Jinja approach) is a documented future item.

## 7. Security model (consolidated)

| Threat | Control |
|---|---|
| PII (`content.private/`) read via any tool | `read_cv` has no `private_path` param (hard `None`); `copytree` copies `content/` only; `list_content_files` returns relative paths with `content.private` filtered post-`resolve()` |
| Path traversal `../`, multi-hop, absolute | `_safe_content_path`: reject absolute + `..`/dot segments before resolution |
| Symlink escape `content/x.yaml → content.private/…` | `.resolve()` then containment check (resolved must be under `content/`) |
| Shell injection via `which` | Whitelist enum + `subprocess.run([...], shell=False)`; never string-interpolate |
| Silent bad edit reaching CI | Full-tree `validate_tree` gate in both propose and apply; apply writes only on zero errors |
| Unconfirmed destructive write | `apply_edit` `destructiveHint=True`; propose→apply two-phase split |
| Runaway subprocess | `timeout=600`, output captured |

Each row has a corresponding test (§8).

## 8. Testing plan (TDD — tests first)

`tests/test_agent_core.py`:

| Test | Asserts |
|---|---|
| `test_read_cv_never_leaks_pii` | with a `content.private/` present in a fixture, `read_cv` output (recursively scanned) contains no phone/address values or `private`-overlay keys |
| `test_read_cv_section_filter` | valid section returns sub-tree; unknown section raises `ValueError`; `None` returns full tree |
| `test_read_cv_rejects_bad_target` | non-`TARGETS` target raises `ValueError` |
| `test_list_content_files_relative_sorted` | returns sorted content-relative `*.yaml`, excludes `content.private/` and `publications.bib`, no absolute paths |
| `test_list_content_files_excludes_symlink_to_private` | a `content/link.yaml → content.private/private.yaml` symlink is not returned |
| `test_safe_path_rejects_absolute / _dotdot / _symlink_escape / _content_private / _non_yaml` | each raises `ValueError` |
| `test_propose_edit_clean_change` | valid edit → `valid=True`, non-empty `diff`, **real file unchanged on disk** |
| `test_propose_edit_schema_break` | bad edit → `valid=False`, `errors` non-empty, file unchanged |
| `test_propose_edit_parity_break` | `L1.de.yaml`-only change that breaks EN/DE parity → `valid=False` |
| `test_propose_edit_no_tempdir_leak` | after the call, no temp dirs remain (cleanup) |
| `test_apply_edit_writes_on_valid` | valid edit → `applied=True`, file content updated, tree still validates |
| `test_apply_edit_refuses_invalid` | bad edit → `applied=False`, file byte-identical to before |
| `test_apply_edit_refuses_private / _traversal` | unsafe paths raise / refuse |
| `test_rerun_renderers_rejects_invalid_which` | `which='formats; rm -rf'` (and any non-whitelist) raises `ValueError` |
| `test_rerun_renderers_validate_first` | invalid tree → `ok=False`, no recipes ran |
| `test_rerun_renderers_skips_missing_tools` | with `typst`/`pnpm` absent (monkeypatched `shutil.which`), `which='all'` → those recipes in `skipped`, `ok=True`, no raise |

> Tests operate on a **copied content tree in `tmp_path`** via the `content_dir` param — never mutating the real `content/`. A shared fixture provides the copy (incl. a fake `content.private/` for PII tests).

`tests/test_mcp_server.py` (`pytest.importorskip("mcp")`):

| Test | Asserts |
|---|---|
| `test_tools_listed` | in-memory MCP client lists exactly the 6 tools with expected names |
| `test_tool_annotations` | each tool carries the §5.1 hints (esp. `apply_edit.destructiveHint=True`, reads `readOnlyHint=True`) |
| `test_get_cv_content_no_pii` | calling `get_cv_content` over the in-memory client returns no PII |
| `test_core_server_parity` | `propose_edit`/`get_cv_content` via the server equal the direct `agent_core` call for the same inputs (anti-drift) |

> Use the `mcp` SDK's **in-memory client/server** test transport (no stdio subprocess) for speed and determinism.

`tests/test_skill_docs.py` (drift-guard, no `mcp` needed):

| Test | Asserts |
|---|---|
| `test_skill_recipes_exist` | every `just <recipe>` token in `SKILL.md`/`reference.md` is a real recipe parsed from the **`justfile`** (regex `^([a-z][a-z0-9-]*):`) |
| `test_skill_sections_exist` | every section/schema-`$def` name the docs cite exists in `cv.schema.json` / the known section list |
| `test_skill_frontmatter_valid` | `SKILL.md` has `name` + `description`; `allowed-tools` reference real recipes |

CI (`ci.yml`): add `uv sync --group mcp`, run the three new test files; keep golden-snapshot job green (rerun must not perturb snapshots — covered because renderers are unchanged).

## 9. Scope

**In (v1):** `agent_core.py` (6 functions + path guard), `mcp_server.py` (6 tools), `.claude/skills/cv/` (`SKILL.md` + `reference.md`), `.mcp.json`, `justfile` recipes, `pyproject` `mcp` group, the three test files, CI wiring, CLAUDE.md update.

**Out (v1) → future:** publishing the skill (`npx skills add …`); auto-generating `SKILL.md`/`reference.md` from schema+justfile; a generic any-CV server; editing `publications.bib`; multi-file atomic edits; any tool touching `refresh-citations`, snapshots, or PII.

## 10. Future directions (documented, not built)

1. **Package & publish the server** — `pipx install`/registry entry; the `content_dir`/`schema_path` params already make the core path-agnostic, so this is mostly packaging + docs.
2. **Auto-generated `reference.md`** — AST/schema → Jinja, mirroring RenderCV, replacing the hand-written cheat-sheet + drift-guard.
3. **Generic any-CV MCP** — schema-agnostic adapter layer (a separate product; explicitly not this).
4. **`.bib` + multi-file atomic edits.**

## 11. File manifest

```
scripts/agent_core.py            new — shared core (6 fns + _safe_content_path)
scripts/mcp_server.py            new — FastMCP wrapper (6 tools, Pydantic models, run())
.claude/skills/cv/SKILL.md       new — agent-facing skill (prose)
.claude/skills/cv/reference.md   new — recipe + schema cheat-sheet (drift-guarded)
.mcp.json                        new — Claude Code project-scoped server config
tests/test_agent_core.py         new
tests/test_mcp_server.py         new
tests/test_skill_docs.py         new
pyproject.toml                   edit — [dependency-groups] mcp; [project.scripts] cv-mcp
justfile                         edit — mcp-server, mcp-dev recipes
.github/workflows/ci.yml         edit — install mcp group, run new tests
CLAUDE.md                        edit — Layout, Commands, Conventions (Agent interface), Phasing row
docs/superpowers/specs/2026-06-03-agent-interface-mcp-skill-design.md   this file
```

## 12. CLAUDE.md update (final plan task)

The implementation plan's last task updates CLAUDE.md: add the new files to **Layout**; add `just mcp-server`/`mcp-dev` to **Commands**; add an **Agent interface** convention ("pure-Python core `scripts/agent_core.py` exposes `read_cv`/`list_content_files`/`propose_edit`/`apply_edit`/`rerun_renderers`; PII never leaks — `read_cv` forces `private_path=None`; skill + MCP server are thin mirrors of the core, guarded against drift"); and add a **Phasing** row (Phase 10 — Agent interface: MCP server + skill over `content/`).

## 13. Acceptance criteria

- `just validate`, `just test`, `just lint` all green (with and without the `mcp` group installed).
- `uv run python -m scripts.mcp_server` starts a stdio server; an MCP client lists the 6 tools with correct annotations.
- An agent (or the in-memory client) can: read a section, propose a valid edit (diff + `valid=True`), apply it (file updated, tree validates), and `rerun_renderers('formats')` rebuilds the machine formats — while every PII/traversal/symlink/injection test passes.
- The skill is invocable (`/cv`), drives the documented edit loop, and its doc drift-guard passes.
- No PII, no `--no-verify`, no hand-edited generated artifacts; atomic commits.
```