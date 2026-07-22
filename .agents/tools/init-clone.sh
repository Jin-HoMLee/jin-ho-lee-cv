#!/usr/bin/env bash
# init-clone.sh — create an independent project-repo clone for a role and wire
# the .claude/memory/ symlink to the sibling claude-personas memory repo.
# With --self, wire the memory repo ITSELF as the Memory Manager's workspace
# (untracked self-mount, no clone).
#
# Run from inside your memory repo (claude-personas-<app>/).

set -euo pipefail

MEMORY_REPO="$( pwd )"
PARENT_DIR="$( dirname "$MEMORY_REPO" )"
MEMORY_REPO_NAME="$( basename "$MEMORY_REPO" )"

usage() {
  cat <<EOF
Usage: $(basename "$0") <role> [--project-url <url>] [--target <path>] [--main] [--force] [--opencode-per-clone]
       $(basename "$0") --self [--force] [--opencode-per-clone]

  role            Role folder in the memory repo (developer, pm, designer, scientist, ...)
  --self          Wire THIS memory repo as the Memory Manager's workspace:
                  an untracked .agents/memory -> ../memory_manager self-mount
                  (plus the .claude/memory hop and vendor adapters). No clone is
                  created; --project-url/--target/--main do not apply. Role
                  identity stays per-workspace: cloning the memory repo does
                  not make anyone the MM.
  --project-url   Project git URL to clone. Falls back to .claude-personas/project.txt, then prompts.
  --target        Explicit target path for the clone. Overrides suffix rules.
  --main          Force this role to claim the no-suffix path \$PARENT/<project-name>/.
  --force         Re-wire the full vendor mount (two-hop memory mount, external Claude Code hop,
                        .codex/hooks.json, opencode.json fallback) in an existing clean clone
                        (must be same project URL).
  --opencode-per-clone  Write a per-clone opencode.json (absolute path) instead of
                        relying on the one-time global ~/.config/opencode/opencode.json
                        instructions entry. Use when OpenCode cannot glob through the
                        .agents/memory symlink (see docs/vendor-caveats.md).

Run from inside your memory repo (claude-personas-<app>/).
EOF
}

# Parse args
ROLE=""
PROJECT_URL=""
TARGET=""
MAIN=0
FORCE=0
SELF=0
OPENCODE_PER_CLONE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --project-url) PROJECT_URL="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --main) MAIN=1; shift ;;
    --force) FORCE=1; shift ;;
    --self) SELF=1; shift ;;
    --opencode-per-clone) OPENCODE_PER_CLONE=1; shift ;;
    -*) echo "Error: unknown flag $1" >&2; usage >&2; exit 1 ;;
    *) if [[ -z "$ROLE" ]]; then ROLE="$1"; shift; else echo "Error: unexpected arg $1" >&2; exit 1; fi ;;
  esac
done

if [[ "$SELF" -eq 1 ]]; then
  # --self always wires memory_manager; a redundant role arg is tolerated,
  # anything else is a contradiction.
  if [[ -n "$ROLE" && "$ROLE" != "memory_manager" ]]; then
    echo "Error: --self always wires the memory_manager role; got role '$ROLE'." >&2
    exit 1
  fi
  if [[ -n "$PROJECT_URL" || -n "$TARGET" || "$MAIN" -eq 1 ]]; then
    echo "Error: --self wires this memory repo in place; --project-url/--target/--main do not apply." >&2
    exit 1
  fi
  ROLE="memory_manager"
elif [[ -z "$ROLE" ]]; then
  usage >&2; exit 1
elif [[ "$ROLE" == "memory_manager" ]]; then
  # The MM's workspace IS the memory repo; a project clone wired to
  # memory_manager/ would recreate the shape-inference confusion (#37/#39).
  echo "Error: the Memory Manager's workspace is the memory repo itself, not a project clone." >&2
  echo "Run '$(basename "$0") --self' from inside the memory repo instead." >&2
  exit 1
fi

# Validate role
ROLE_DIR="$MEMORY_REPO/$ROLE"
if [[ ! -d "$ROLE_DIR" || ! -f "$ROLE_DIR/MEMORY.md" ]]; then
  if [[ "$SELF" -eq 1 ]]; then
    echo "Error: no memory_manager/ role directory with MEMORY.md in $MEMORY_REPO." >&2
    echo "A Memory Manager is a real role dir; create it first:" >&2
    echo "  mkdir memory_manager" >&2
    printf '%s\n' "  printf '# Memory Index - memory_manager\\n' > memory_manager/MEMORY.md" >&2
    echo "  ln -s ../shared memory_manager/shared" >&2
    exit 1
  fi
  echo "Error: role '$ROLE' not found in $MEMORY_REPO/" >&2
  echo "Available roles:" >&2
  for d in "$MEMORY_REPO"/*/; do
    n="$(basename "$d")"
    # Reserved non-role names, case-folded (APFS treats Examples/ as
    # examples/). Keep in sync with doctor.sh is_reserved_name -
    # tests/test_framework_files.sh greps every copy and fails on desync.
    case "$(printf '%s' "$n" | tr '[:upper:]' '[:lower:]')" in
      shared|examples) continue ;;
    esac
    if [[ -f "$d/MEMORY.md" ]]; then
      echo "  $n" >&2
    fi
  done
  exit 1
fi

CONFIG_DIR="$MEMORY_REPO/.claude-personas"
PROJECT_TXT="$CONFIG_DIR/project.txt"

if [[ "$SELF" -eq 1 ]]; then
  # --self: the workspace being wired IS the memory repo. Nothing to clone,
  # no project URL, no suffix rules. Untracked-ness needs .git/info/exclude.
  TARGET="$MEMORY_REPO"
  if [[ ! -d "$TARGET/.git" ]]; then
    echo "Error: $TARGET has no .git/ directory; cannot wire untracked mounts via .git/info/exclude." >&2
    exit 1
  fi
fi

if [[ "$SELF" -ne 1 ]]; then
# Resolve project URL
if [[ -z "$PROJECT_URL" && -f "$PROJECT_TXT" ]]; then
  PROJECT_URL="$(cat "$PROJECT_TXT")"
fi
if [[ -z "$PROJECT_URL" ]]; then
  read -r -p "Project git URL: " PROJECT_URL
fi
if [[ -z "$PROJECT_URL" ]]; then
  echo "Error: project URL is required" >&2
  exit 1
fi

# Derive project name from memory repo name (strip leading claude-personas-)
PROJECT_NAME="${MEMORY_REPO_NAME#claude-personas-}"

if [[ "$PROJECT_NAME" == "$MEMORY_REPO_NAME" ]]; then
  # Fallback: derive from project URL basename
  PROJECT_NAME="$(basename "$PROJECT_URL")"
  PROJECT_NAME="${PROJECT_NAME%.git}"
fi

# Determine no-suffix claimer
MAIN_ROLE_TXT="$CONFIG_DIR/main-role.txt"
DEFAULT_MAIN="developer"
if [[ -f "$MAIN_ROLE_TXT" ]]; then
  DEFAULT_MAIN="$(cat "$MAIN_ROLE_TXT")"
fi

CLAIMS_NO_SUFFIX=0
NO_SUFFIX_PATH="$PARENT_DIR/$PROJECT_NAME"
if [[ "$MAIN" -eq 1 ]] || [[ "$ROLE" == "$DEFAULT_MAIN" ]]; then
  if [[ ! -e "$NO_SUFFIX_PATH" ]] || [[ "$FORCE" -eq 1 ]]; then
    CLAIMS_NO_SUFFIX=1
  elif [[ "$MAIN" -eq 1 ]]; then
    # Explicit --main: fail rather than silently fall back to suffix.
    echo "Error: --main requested but '$NO_SUFFIX_PATH' already exists." >&2
    echo "Pass --force to re-wire .claude/memory/ in place, or remove/rename the existing directory." >&2
    exit 1
  fi
fi

# Resolve target
if [[ -z "$TARGET" ]]; then
  if [[ "$CLAIMS_NO_SUFFIX" -eq 1 ]]; then
    TARGET="$NO_SUFFIX_PATH"
  else
    TARGET="$PARENT_DIR/$PROJECT_NAME-$ROLE"
  fi
fi

# Validate target
if [[ -e "$TARGET" && "$FORCE" -ne 1 ]]; then
  echo "Error: target '$TARGET' already exists. Use --force or --target to override." >&2
  exit 1
fi
fi # end clone-mode-only: URL/suffix/target resolution

# Track whether THIS run created the clone — governs rollback on a later
# failure. A pre-existing clone (reused via --force) must never be deleted.
CREATED_CLONE=0

# Roll back a clone WE created this run (spec error table: "rollback by
# removing the target clone if we created it this run"). No-op for a clone
# reused via --force, since CREATED_CLONE stays 0 there. The -n/-d guards are
# defensive belt-and-suspenders on top of that invariant.
rollback_fresh_clone() {
  # --self never clones: TARGET is the user's memory repo and must never be
  # removed, whatever CREATED_CLONE says.
  if [[ "$SELF" -eq 1 ]]; then return 0; fi
  if [[ "$CREATED_CLONE" -eq 1 && -n "$TARGET" && -d "$TARGET" ]]; then
    rm -rf "$TARGET"
    echo "✓ Rolled back freshly-created clone at $TARGET" >&2
  fi
}

if [[ "$SELF" -eq 1 ]]; then
  : # --self: no clone to create or verify; wiring targets the memory repo itself.
elif [[ -e "$TARGET" && "$FORCE" -eq 1 ]]; then
  # Must be a clean git checkout of the same project URL
  if [[ ! -d "$TARGET/.git" ]]; then
    echo "Error: '$TARGET' exists but is not a git repo. Refusing --force." >&2
    exit 1
  fi
  EXISTING_URL="$( cd "$TARGET" && git config --get remote.origin.url 2>/dev/null || echo "" )"
  if [[ "$EXISTING_URL" != "$PROJECT_URL" ]]; then
    echo "Error: '$TARGET' is a clone of '$EXISTING_URL', not '$PROJECT_URL'. Refusing --force." >&2
    exit 1
  fi
  echo "✓ --force: existing clone at '$TARGET' matches project URL; will only re-wire .claude/memory/"
else
  # Clone fresh
  echo "Cloning $PROJECT_URL → $TARGET"
  git clone "$PROJECT_URL" "$TARGET"
  CREATED_CLONE=1
fi

# --- Helpers for wiring ------------------------------------------------------

# Idempotently append a line to the clone's .git/info/exclude (per-clone
# untracked-ness that never dirties the project repo - spec decision log).
EXCLUDE_FILE="$TARGET/.git/info/exclude"
add_exclude() {
  mkdir -p "$(dirname "$EXCLUDE_FILE")"
  touch "$EXCLUDE_FILE"
  grep -qxF "$1" "$EXCLUDE_FILE" 2>/dev/null || printf '%s\n' "$1" >> "$EXCLUDE_FILE"
}

# Per-vendor failures report and continue - one vendor's problem must not
# kill the other two (spec: init-clone.sh changes, last bullet).
VENDOR_WARNINGS=0
vendor_warn() {
  echo "WARN: $*" >&2
  VENDOR_WARNINGS=$((VENDOR_WARNINGS + 1))
}

# --- Core mount (vendor-neutral, rollback-protected) --------------------------
# .agents/memory -> ../../<memory-repo>/<role>   (the single role signal)
# .claude/memory -> ../.agents/memory            (Claude Code in-repo hop)
# A failure anywhere in this window must roll back a clone we created this run.

if ! mkdir -p "$TARGET/.agents"; then
  echo "Error: failed to create $TARGET/.agents" >&2
  rollback_fresh_clone
  exit 1
fi

# Aliased layout (#81): a consumer that canonicalizes on .agents/ and
# commits '.claude -> .agents' (one dir, two names). Under that aliasing
# .claude/memory IS .agents/memory, so the hop must not be written: ln
# would dereference through the alias onto the mount (a symlink to the
# role DIRECTORY) and plant the link INSIDE the memory repo's role dir.
# Detect the alias - materialized (-ef) or the committed link text on a
# fresh clone whose .agents/ only just got created above - and skip the
# hop and its exclude line below; the mount alone satisfies both paths.
# Keep in sync with doctor.sh claude_aliases_agents.
CLAUDE_ALIASED=0
if [[ "$TARGET/.claude" -ef "$TARGET/.agents" ]] || \
   { [[ -L "$TARGET/.claude" ]] && [[ "$(readlink "$TARGET/.claude")" == ".agents" ]]; }; then
  CLAUDE_ALIASED=1
elif ! mkdir -p "$TARGET/.claude"; then
  echo "Error: failed to create $TARGET/.claude" >&2
  rollback_fresh_clone
  exit 1
fi
AGENTS_LINK="$TARGET/.agents/memory"
MEMORY_LINK="$TARGET/.claude/memory"

# Migrate v3.0 layout: legacy root symlink -> back up under .claude/
# (clone mode only: in the memory repo a root memory/ path is user content)
LEGACY_LINK="$TARGET/memory"
if [[ "$SELF" -ne 1 && "$FORCE" -eq 1 && ( -L "$LEGACY_LINK" || -e "$LEGACY_LINK" ) ]]; then
  LEGACY_BACKUP="$TARGET/.claude/memory.legacy-backup-$(date +%Y%m%d-%H%M%S)"
  # Checked mv: bare failure under set -e would skip rollback_fresh_clone.
  if ! mv "$LEGACY_LINK" "$LEGACY_BACKUP"; then
    echo "Error: failed to migrate legacy root memory/ → $LEGACY_BACKUP" >&2
    rollback_fresh_clone
    exit 1
  fi
  echo "✓ Migrated legacy root memory/ → $LEGACY_BACKUP"
fi

# Back up whatever sits at either mount point (v3.1 direct symlink on a
# --force migration, or artifacts from a prior run). On an aliased clone
# MEMORY_LINK is the same inode as AGENTS_LINK - handling it separately
# would double-move one file, so it is skipped there.
MOUNT_POINTS=("$AGENTS_LINK")
if [[ "$CLAUDE_ALIASED" -ne 1 ]]; then
  MOUNT_POINTS+=("$MEMORY_LINK")
fi
for link in "${MOUNT_POINTS[@]}"; do
  if [[ -e "$link" || -L "$link" ]]; then
    if [[ "$FORCE" -eq 1 ]]; then
      BACKUP="$link.backup-$(date +%Y%m%d-%H%M%S)"
      # Checked mv: a bare failure under set -e would exit without honoring
      # the rollback invariant for the post-clone wiring window.
      if ! mv "$link" "$BACKUP"; then
        echo "Error: failed to back up ${link#"$TARGET"/} → ${BACKUP#"$TARGET"/}" >&2
        rollback_fresh_clone
        exit 1
      fi
      echo "✓ Backed up existing ${link#"$TARGET"/} → ${BACKUP#"$TARGET"/}"
    else
      echo "Error: $link already exists. Use --force to back up." >&2
      rollback_fresh_clone
      exit 1
    fi
  fi
done

# Relative symlink targets resolve against .agents/, so the self-mount is
# ../memory_manager (one level up = the memory repo root), not ./memory_manager.
if [[ "$SELF" -eq 1 ]]; then
  MOUNT_TARGET="../$ROLE"
else
  MOUNT_TARGET="../../$MEMORY_REPO_NAME/$ROLE"
fi
# ln -sn everywhere: -n keeps ln from dereferencing a symlink-to-dir at the
# destination and silently creating INSIDE the resolved directory - the #81
# contamination mode. With -n such a state fails loudly instead.
if ! ln -sn "$MOUNT_TARGET" "$AGENTS_LINK"; then
  echo "Error: failed to create memory mount $AGENTS_LINK" >&2
  rollback_fresh_clone
  exit 1
fi
echo "✓ Symlinked .agents/memory → $MOUNT_TARGET"

if [[ "$CLAUDE_ALIASED" -eq 1 ]]; then
  echo "✓ .claude aliases .agents - Claude Code hop satisfied transitively (nothing to write)"
elif ! ln -sn "../.agents/memory" "$MEMORY_LINK"; then
  echo "Error: failed to create Claude Code hop $MEMORY_LINK" >&2
  rollback_fresh_clone
  exit 1
else
  echo "✓ Symlinked .claude/memory → ../.agents/memory"
fi

# Untracked-ness via exclude, NOT .gitignore. Existing committed v3.1
# .gitignore lines keep working; we just stop adding new ones. NOTE the
# entries have no trailing slash: a trailing slash matches only real
# directories, and these paths are symlinks.
add_exclude "# claude-personas vendor wiring (per-clone, untracked)"
add_exclude "/.agents/memory"
# On an aliased clone /.claude/memory never exists as its own git entry -
# doctor (#80) likewise skips the line there.
if [[ "$CLAUDE_ALIASED" -ne 1 ]]; then
  add_exclude "/.claude/memory"
fi

# Remove legacy /memory/ line on --force (v3.0 -> v3.1 migration) - unchanged.
GITIGNORE="$TARGET/.gitignore"
if [[ "$FORCE" -eq 1 && -f "$GITIGNORE" ]] && grep -qE '^/?memory/?$' "$GITIGNORE"; then
  grep -vE '^/?memory/?$' "$GITIGNORE" > "$GITIGNORE.tmp" || true
  # Checked mv: bare failure under set -e would skip rollback_fresh_clone.
  if ! mv "$GITIGNORE.tmp" "$GITIGNORE"; then
    echo "Error: failed to rewrite $GITIGNORE (removing legacy /memory/ line)" >&2
    rollback_fresh_clone
    exit 1
  fi
  echo "✓ Removed legacy /memory/ from $GITIGNORE"
fi

# Persist project URL (clone mode only; --self has none)
if [[ "$SELF" -ne 1 ]]; then
  mkdir -p "$CONFIG_DIR"
  if [[ ! -f "$PROJECT_TXT" ]]; then
    echo "$PROJECT_URL" > "$PROJECT_TXT"
    echo "✓ Saved project URL to $PROJECT_TXT"
  fi
fi

# --- Claude Code external hop -------------------------------------------------
# CC's auto-memory loader reads ~/.claude/projects/<slug>/memory, NOT the
# in-repo path (latent v3.1 gap found in spec self-review). <slug> is CC's
# own derivation of the clone's absolute physical path: '/' and '.' each
# become '-' (live test 4 in docs/vendor-caveats.md re-verifies this).
# Report-and-continue: a refusal here must not kill Codex/OpenCode wiring.
wire_cc_external_hop() {
  local clone_abs slug proj_dir ext expected
  clone_abs="$(cd "$TARGET" && pwd -P)" || { vendor_warn "Claude Code: cannot resolve clone path"; return 0; }
  slug="$(printf '%s' "$clone_abs" | tr '/.' '-')"
  proj_dir="$HOME/.claude/projects"
  ext="$proj_dir/$slug/memory"
  expected="$clone_abs/.claude/memory"

  if [[ -L "$ext" ]]; then
    if [[ "$(readlink "$ext")" == "$expected" ]]; then
      echo "✓ External Claude Code hop already wired: $ext"
    elif ln -sfn "$expected" "$ext"; then
      echo "✓ Repaired external Claude Code hop: $ext → $expected"
    else
      vendor_warn "Claude Code: could not repair external hop $ext"
    fi
  elif [[ -d "$ext" ]]; then
    if [[ -z "$(ls -A "$ext")" ]] && rmdir "$ext" 2>/dev/null && ln -s "$expected" "$ext"; then
      echo "✓ Replaced empty directory with external Claude Code hop: $ext"
    else
      vendor_warn "Claude Code: $ext is a real directory that could not be replaced (non-empty or unreadable) - refusing to touch; reconcile by hand (auto-memory may have been written there), then re-run with --force"
    fi
  elif [[ -e "$ext" ]]; then
    vendor_warn "Claude Code: $ext exists and is neither symlink nor directory - refusing to touch"
  else
    if mkdir -p "$proj_dir/$slug" && ln -s "$expected" "$ext"; then
      echo "✓ Symlinked external Claude Code hop: $ext → $expected"
    else
      vendor_warn "Claude Code: could not create external hop $ext"
    fi
  fi
  return 0
}

wire_cc_external_hop

# --- Codex adapter -------------------------------------------------------------
# Per-clone generated hooks.json with ABSOLUTE paths (cerebrum pattern); the
# inject script ships in the memory repo so all of that project's clones share
# one copy. Trust is two-layer and NOT scriptable: repo trust + per-hook
# /hooks review, re-triggered whenever the generated file changes.
CODEX_WIRED=0
wire_codex_adapter() {
  local inject="$MEMORY_REPO/.agents/hooks/lib/inject-role-index.sh"
  local hooks="$TARGET/.codex/hooks.json"
  # Refuse-and-warn: $inject and $ROLE_DIR are embedded verbatim in the JSON
  # below with no escaper (jq dependency deliberately avoided) - a quote or
  # backslash would silently produce invalid JSON, and a single quote would
  # additionally break the single-quoted shell command string.
  case "$inject$ROLE_DIR" in (*[\"\\\']*)
    vendor_warn "Codex: memory-repo path contains a quote or backslash - cannot embed safely in hooks.json; skipping"
    return 0 ;;
  esac
  if [[ ! -x "$inject" ]]; then
    vendor_warn "Codex: $inject missing or not executable (install/update the framework payload in the memory repo) - .codex/hooks.json not generated"
    return 0
  fi
  if [[ -e "$hooks" && "$FORCE" -ne 1 ]]; then
    vendor_warn "Codex: $hooks already exists - re-run with --force to back up and regenerate"
    return 0
  fi
  if [[ -e "$hooks" ]]; then
    # Checked mv: vendor failures must WARN-and-continue (exit-2 contract),
    # not die via set -e.
    if ! mv "$hooks" "$hooks.backup-$(date +%Y%m%d-%H%M%S)"; then
      vendor_warn "Codex: could not back up existing $hooks - leaving it in place"
      return 0
    fi
    echo "✓ Backed up existing .codex/hooks.json"
  fi
  if ! mkdir -p "$TARGET/.codex"; then
    vendor_warn "Codex: cannot create $TARGET/.codex"
    return 0
  fi
  if ! cat > "$hooks" <<EOF
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "'$inject' '$ROLE_DIR'",
            "timeout": 10,
            "statusMessage": "Injecting role memory index…"
          }
        ]
      }
    ]
  }
}
EOF
  then
    vendor_warn "Codex: could not write $hooks"
    return 0
  fi
  add_exclude "/.codex/hooks.json"
  echo "✓ Generated .codex/hooks.json (role: $ROLE)"
  CODEX_WIRED=1
  return 0
}

wire_codex_adapter

if [[ "$CODEX_WIRED" -eq 1 ]]; then
  echo ""
  echo "Codex one-time steps (not scriptable):"
  echo "  1. Open Codex in $TARGET and accept the repo trust prompt."
  echo "  2. Run /hooks in Codex and approve the generated SessionStart hook."
  echo "     (Re-approval is required whenever .codex/hooks.json changes.)"
fi

# --- OpenCode adapter ----------------------------------------------------------
# Preferred wiring is GLOBAL and one-time (spec decision log): a relative
# "instructions" entry resolves against each session's project dir, so a
# single entry serves every wired clone. Gated on OpenCode's symlink-glob
# behavior (live test 1) - the per-clone absolute-path file is the fallback.
OPENCODE_GLOBAL_NOTE=0
wire_opencode_adapter() {
  if [[ "$OPENCODE_PER_CLONE" -ne 1 ]]; then
    OPENCODE_GLOBAL_NOTE=1
    return 0
  fi
  local oc="$TARGET/opencode.json" clone_abs
  clone_abs="$(cd "$TARGET" && pwd -P)" || { vendor_warn "OpenCode: cannot resolve clone path"; return 0; }
  # Refuse-and-warn: $clone_abs is embedded verbatim in the JSON below with
  # no escaper (jq dependency deliberately avoided) - a quote or backslash
  # would silently produce invalid JSON.
  case "$clone_abs" in (*[\"\\]*)
    vendor_warn "OpenCode: clone path contains a quote or backslash - cannot embed safely in opencode.json; skipping"
    return 0 ;;
  esac
  if [[ -e "$oc" && "$FORCE" -ne 1 ]]; then
    vendor_warn "OpenCode: $oc already exists - re-run with --force to back up and regenerate"
    return 0
  fi
  if [[ -e "$oc" ]]; then
    # Checked mv: same WARN-and-continue contract as the Codex backup.
    if ! mv "$oc" "$oc.backup-$(date +%Y%m%d-%H%M%S)"; then
      vendor_warn "OpenCode: could not back up existing $oc - leaving it in place"
      return 0
    fi
    echo "✓ Backed up existing opencode.json"
  fi
  if ! printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "instructions": ["%s"]\n}\n' "$clone_abs/.agents/memory/MEMORY.md" > "$oc"; then
    vendor_warn "OpenCode: could not write $oc"
    return 0
  fi
  add_exclude "/opencode.json"
  echo "✓ Wrote per-clone opencode.json (absolute instructions path)"
  return 0
}

wire_opencode_adapter

if [[ "$OPENCODE_GLOBAL_NOTE" -eq 1 ]]; then
  echo ""
  echo "OpenCode one-time step (per machine, serves every wired clone):"
  echo "  Add \".agents/memory/MEMORY.md\" to the \"instructions\" array in"
  echo "  ~/.config/opencode/opencode.json"
  echo "  (If OpenCode does not load it through the symlink, re-run with"
  echo "   --opencode-per-clone; see docs/vendor-caveats.md.)"
fi

echo ""
if [[ "$VENDOR_WARNINGS" -gt 0 ]]; then
  echo "Done with $VENDOR_WARNINGS vendor warning(s) - see WARN lines above. Core mount is wired."
  exit 2
fi
if [[ "$SELF" -eq 1 ]]; then
  echo "Done. This memory repo is wired as the memory_manager workspace (untracked self-mount)."
else
  echo "Done. Open $TARGET in Claude Code → role memory loads via .claude/memory → .agents/memory."
fi
