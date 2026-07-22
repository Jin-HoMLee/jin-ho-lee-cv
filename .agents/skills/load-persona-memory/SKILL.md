---
name: load-persona-memory
description: Use when working in a repo wired to a personas memory repo (role clones or the memory repo itself), especially requests to load or refresh role/shared memory, follow MEMORY.md links, or resolve which role this workspace is - works identically from Claude Code, Codex, and OpenCode.
---

# Load Persona Memory

## Purpose

Read repo-backed persona memory (the claude-personas pattern) from any of the three supported tools.
The memory repo is the source of truth.
Do not mirror memory into tool-native stores (Codex `~/.codex/memories/`, etc.) and do not treat tool-generated memories as persona guidance.

## Discovery

Resolve the memory repo and role before reading memory, in this order - first hit wins.

1. Read the workspace's `.agents/memory` symlink target: the target directory name is the role, the target path is the memory repo.
   In the memory repo itself this is the Memory Manager's self-mount (`.agents/memory -> ../memory_manager`, wired by `init-clone.sh --self`; today the tool lives at `framework/tools/init-clone.sh` in the framework repo or a memory repo created from it, and will land at `.agents/tools/init-clone.sh` once the installer ships), so `memory_manager` resolves here exactly like any other role.
2. Else read `.claude/memory` the same way (v3.1 legacy direct symlink).
3. Else enumerate candidates: every sibling directory of the workspace (same parent dir) containing a `.claude-personas/project.txt` marker.
   Verify each by comparing the workspace's `origin` remote against that `project.txt`.
   Normalize both sides to a canonical `owner/repo` before comparing: strip a leading `git@<host>:`, `ssh://git@<host>/`, or `https://<host>/` prefix and any trailing `.git`, so the scp-like SSH, scheme SSH, and HTTPS forms of the same remote compare equal.
   Exactly one match wins; zero or multiple matches fail with a report, never a guess.
4. If the workspace looks like a memory repo (it has `.claude-personas/` or role dirs with `MEMORY.md` files) but steps 1-3 found no wiring, do not assume any role - not even `memory_manager`.
   Report that this looks like an unwired memory repo and ask: if the user is the Memory Manager, they run `init-clone.sh --self` (which declares MM via the self-mount); otherwise they say which role to act as.
   Repo shape is not a role declaration; this step never resolves a role on its own.
5. Last resort: clone-naming conventions as implemented by `init-clone.sh` - the no-suffix clone is the main role (`.claude-personas/main-role.txt` when present, else `developer`); suffix clones are `<project>-<role>`.

Validate that `<memory-repo>/<role>/MEMORY.md` exists before proceeding.
This applies to `memory_manager` like any other role: a Memory Manager is a real role with its own `memory_manager/` directory in the memory repo, declared by the self-mount and never inferred from repo shape.
If validation fails (dangling mount, missing role dir), report that and ask which role to act as; do not guess or synthesize a role.

## Read Order

Every time persona memory is needed, issue fresh file-read tool calls.
Do not rely on prior same-session reads.

Read these indices first:

```text
<memory-repo>/<role>/MEMORY.md
<memory-repo>/<role>/shared/MEMORY.md
<memory-repo>/<role>/user/MEMORY.md   (only when the user mount exists)
```

This includes `memory_manager` - its role directory is standard (own `MEMORY.md`, own `shared` symlink), so no special read order applies.

Treat the role index and shared index as routing tables.
When `<role>/user` exists, it is the role@user mount - this role's cross-project home (claude-personas#49).
Read its index third; the reading order mirrors the precedence chain (role@project > project > role@user), so on conflict the earlier read wins.
A missing `<role>/user` is normal (the mount is lazy), never an error.
Read linked files only when relevant to the current task.

## Path Rules

Persona memory paths are file-relative.

- A bare filename in `<role>/MEMORY.md` resolves inside `<role>/`.
- A `shared/<file>` link from `<role>/MEMORY.md` resolves through `<role>/shared`, which points at `../shared`.
- A bare filename in `shared/MEMORY.md` resolves inside `shared/`.
- `<!-- src: ... -->` annotations follow the same file-relative rule.
- A `user/<file>` link from `<role>/MEMORY.md` resolves through `<role>/user`, which points at this role's dir in the user-scope roles instance (the manifest's `role_source`).

Do not invent paths under tool-native memory stores when the repo-backed path is available.

## Governance

Reading persona memory is always allowed.

Do not edit, commit, or push a memory repo unless the user explicitly asks for that action.
If editing is requested, respect the memory repo governance:

- A role session may edit its own `<role>/` directory and `shared/` when explicitly requested.
- If the project has a Memory Manager, the Memory Manager is the sole committer and pusher of the memory repo.
- Do not touch another role's directory from a role session unless the user explicitly asks and the change is mechanical or stewardship-oriented.
- The `<role>/user` mount is read-only by convention: a promotion to role@user is an explicit write into the user-scope roles instance (`role_source` target), committed in THAT repo - never through the symlink as part of a project-memory commit.

If the memory repo has unrelated dirty changes, leave them alone.

## Per-Tool Role of This Skill

- Claude Code: mid-session refresh (re-read the indices from disk when memory may have changed) and the escape hatch from unwired directories.
- Codex: the lazy-read complement to the SessionStart index injection, and the fallback when the `.codex/` hooks layer is not yet trusted.
- OpenCode: the lazy-read complement to the `instructions`-loaded index.

For a memory freshness check: fresh-read the role and shared indices (and the user index when the mount exists), report only meaningful changes, and respond exactly `Memory check complete` when no meaningful changes are found.
