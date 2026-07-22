#!/usr/bin/env bash
# doctor.sh - manifest-driven integrity check + fixer for a claude-personas
# instance (role-clone constellation, embedded, or user-tier).
#
# Usage:
#   doctor.sh [--check] [--root PATH]
#   doctor.sh --init <topology>
#
# The instance declares its topology in a committed $root/.agents/manifest
# file (flat key=value, never shell-sourced). doctor.sh never infers the
# topology from repo shape - see docs/superpowers/specs/
# 2026-07-04-toolbox-manifest-driven-doctor-design.md.
#
# Default mode fixes derivable drift; --check reports only and changes
# nothing. Output vocabulary is exactly DRIFT: / FIXED: / ERROR: / OK:.
# Exit codes: 0 clean, 1 drift or error, 2 missing/invalid manifest.
#
# Never uses `set -e`: one refusal must not hide others.
#
# OPENCODE_MODE is consumed by topology_role_clones_checks' vendor wiring
# (Task 6): it selects the opencode adapter's per-clone vs. global check.
# CHECK / MEMORY_LAYOUT / CLAUDE_HOOKS / CODEX_HOOKS are consumed by this
# file's shared check core (need_link, check_payload, check_hook_scripts).
# ADAPTERS and SKILLS_MOUNT are consumed by topology_user_tier_checks
# (Task 3), topology_embedded_checks (Task 4), and topology_role_clones_checks
# (Task 6).
set -u

# --- constants: the manifest key vocabulary (the validation whitelist) ---

VALID_TOPOLOGIES="role-clones embedded user-tier"
VALID_MEMORY_LAYOUTS="roles flat"
VALID_ADAPTER_VALUES="claude-code codex opencode pi"
VALID_SKILLS_MOUNT_VALUES="true false"
VALID_OPENCODE_VALUES="global per-clone"
SUPPORTED_MANIFEST_VERSIONS="1"

# All keys this doctor understands, regardless of topology.
ALL_VALID_KEYS="manifest_version topology memory_layout adapter claude_hook codex_hook pi_extension skills_mount opencode framework_source framework_ref role_source"

# Keys valid only for topology=embedded.
EMBEDDED_ONLY_KEYS="claude_hook codex_hook pi_extension skills_mount"
# Keys valid only for topology=role-clones.
ROLE_CLONES_ONLY_KEYS="opencode"

usage() {
  cat <<'EOF'
Usage: doctor.sh [--check] [--root PATH]
       doctor.sh --init <topology>

  --check         Report only; do not fix anything. Exits nonzero on drift.
  --root PATH     Instance root to doctor (default: git toplevel of cwd, or cwd).
  --init TOPOLOGY Write a starter .agents/manifest for TOPOLOGY and exit.
                  TOPOLOGY is one of: role-clones, embedded, user-tier.
                  Refuses to overwrite an existing manifest.

Exit codes: 0 clean, 1 drift or error, 2 missing/invalid manifest.
EOF
}

_word_in_list() {
  # _word_in_list <word> <space-separated-list>
  local word="$1" list="$2"
  case " $list " in
    *" $word "*) return 0 ;;
    *) return 1 ;;
  esac
}

# --- argument parsing ---

CHECK=0
ROOT_ARG=""
INIT_TOPOLOGY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --check)
      CHECK=1
      shift
      ;;
    --root)
      if [ $# -lt 2 ]; then
        echo "ERROR: --root requires a PATH argument" >&2
        exit 2
      fi
      ROOT_ARG="$2"
      shift 2
      ;;
    --init)
      if [ $# -lt 2 ]; then
        echo "ERROR: --init requires a TOPOLOGY argument" >&2
        exit 2
      fi
      INIT_TOPOLOGY="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# --- root resolution ---

default_root() {
  local toplevel
  toplevel="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -n "$toplevel" ]; then
    printf '%s\n' "$toplevel"
    return 0
  fi
  pwd
}

if [ -n "$ROOT_ARG" ]; then
  ROOT="$(cd "$ROOT_ARG" 2>/dev/null && pwd)"
  if [ -z "$ROOT" ]; then
    echo "ERROR: --root path does not exist: $ROOT_ARG" >&2
    exit 2
  fi
else
  ROOT="$(default_root)"
fi

MANIFEST="$ROOT/.agents/manifest"

# --- manifest readers (grep/cut line readers; the manifest is never sourced) ---

manifest_get() {
  # First value for key $1 (non-comment, non-blank lines only).
  local key="$1"
  grep -v '^[[:space:]]*#' "$MANIFEST" 2>/dev/null \
    | grep -v '^[[:space:]]*$' \
    | grep "^${key}=" \
    | head -n1 \
    | cut -d= -f2-
}

manifest_get_all() {
  # All values for repeatable key $1, one per line.
  local key="$1"
  grep -v '^[[:space:]]*#' "$MANIFEST" 2>/dev/null \
    | grep -v '^[[:space:]]*$' \
    | grep "^${key}=" \
    | cut -d= -f2-
}

# --- starter manifests for --init ---

write_starter_role_clones() {
  cat > "$1" <<'EOF'
# claude-personas manifest - written by doctor.sh --init role-clones
# Flat key=value, strict (no spaces around =); # comments and blank lines
# are ignored. See docs/superpowers/specs/
# 2026-07-04-toolbox-manifest-driven-doctor-design.md for the full key table.

manifest_version=1
topology=role-clones
memory_layout=roles

# Declare each vendor adapter this instance wires. Remove a line if that
# vendor is not used here.
adapter=claude-code
adapter=codex
adapter=opencode

# Optional keys for topology=role-clones:
# opencode=global      # or: per-clone (default: global)
EOF
}

write_starter_embedded() {
  cat > "$1" <<'EOF'
# claude-personas manifest - written by doctor.sh --init embedded
# Flat key=value, strict (no spaces around =); # comments and blank lines
# are ignored. See docs/superpowers/specs/
# 2026-07-04-toolbox-manifest-driven-doctor-design.md for the full key table.

manifest_version=1
topology=embedded
memory_layout=flat

# Declare each vendor adapter this instance wires. Remove a line if that
# vendor is not used here.
adapter=claude-code
adapter=codex
adapter=opencode
# adapter=pi    # uncomment together with the pi_extension key below

# Optional keys for topology=embedded:
# claude_hook=.agents/hooks/some-hook.sh   # repeatable; repo-relative script path
# codex_hook=.agents/hooks/some-hook.sh    # repeatable; repo-relative script path
# pi_extension=.agents/hooks/lib/pi-inject-memory-index.ts   # repeatable; repo-relative module path
# skills_mount=true                  # or: false (default)
EOF
}

write_starter_user_tier() {
  cat > "$1" <<'EOF'
# claude-personas manifest - written by doctor.sh --init user-tier
# Flat key=value, strict (no spaces around =); # comments and blank lines
# are ignored. See docs/superpowers/specs/
# 2026-07-04-toolbox-manifest-driven-doctor-design.md for the full key table.

manifest_version=1
topology=user-tier
memory_layout=flat

# Declare each vendor adapter this instance wires. Remove a line if that
# vendor is not used here.
adapter=claude-code
adapter=codex
adapter=opencode

# No topology-specific optional keys for user-tier.
EOF
}

do_init() {
  local topology="$1"

  if ! _word_in_list "$topology" "$VALID_TOPOLOGIES"; then
    echo "ERROR: unknown topology '$topology' for --init (valid: role-clones, embedded, user-tier)" >&2
    exit 2
  fi

  if [ -e "$MANIFEST" ]; then
    echo "ERROR: manifest already exists at $MANIFEST (refusing to overwrite; edit it directly)" >&2
    exit 2
  fi

  mkdir -p "$(dirname "$MANIFEST")"

  case "$topology" in
    role-clones) write_starter_role_clones "$MANIFEST" ;;
    embedded) write_starter_embedded "$MANIFEST" ;;
    user-tier) write_starter_user_tier "$MANIFEST" ;;
  esac

  echo "Wrote starter manifest: $MANIFEST"
  exit 0
}

if [ -n "$INIT_TOPOLOGY" ]; then
  do_init "$INIT_TOPOLOGY"
fi

# --- refuse if there is no manifest to doctor (static, never inspects repo shape) ---

if [ ! -f "$MANIFEST" ]; then
  cat >&2 <<EOF
ERROR: no manifest at $MANIFEST
This instance has not declared its topology. doctor.sh never guesses the
topology from repo shape - declare it explicitly. Supported topologies:

  role-clones  memory repo + per-role clones (the claude-personas constellation)
  embedded     a single repo carries .agents/ alongside its own project code
  user-tier    global user-level memory, not tied to a single project repo

Run: doctor.sh --init <topology>   (role-clones | embedded | user-tier)
EOF
  exit 2
fi

# --- manifest validation ---

validate_manifest_syntax() {
  # Pass 1: strict line syntax + unknown-key check over the raw file.
  # Every non-comment, non-blank line must match ^[a-z_]+=[^[:space:]]+$
  # (no spaces around =, non-empty value, no embedded whitespace, no
  # trailing whitespace). Comment/blank lines are ignored outright.
  local line lineno=0 key trimmed
  while IFS= read -r line || [ -n "$line" ]; do
    lineno=$((lineno + 1))

    # Blank (or whitespace-only) line: ignored.
    if [ -z "${line//[[:space:]]/}" ]; then
      continue
    fi

    # Comment line: ignored, even when indented - only a pure key=value line
    # is held to the no-leading/trailing-whitespace rule.
    trimmed="$line"
    while true; do
      case "$trimmed" in
        [\ $'\t']*) trimmed="${trimmed#?}" ;;
        *) break ;;
      esac
    done
    case "$trimmed" in
      '#'*) continue ;;
    esac

    if ! printf '%s\n' "$line" | grep -qE '^[a-z_]+=[^[:space:]]+$'; then
      echo "ERROR: invalid manifest line $lineno in $MANIFEST: '$line' (expected strict key=value, no spaces)" >&2
      exit 2
    fi

    key="${line%%=*}"
    if ! _word_in_list "$key" "$ALL_VALID_KEYS"; then
      echo "ERROR: unknown manifest key '$key' (line $lineno in $MANIFEST: $line)" >&2
      exit 2
    fi
  done < "$MANIFEST"
}

validate_manifest_semantics() {
  local k v version topology layout adapter_value hook

  # Required keys present.
  for k in manifest_version topology memory_layout; do
    v="$(manifest_get "$k")"
    if [ -z "$v" ]; then
      echo "ERROR: missing required manifest key '$k' in $MANIFEST" >&2
      exit 2
    fi
  done

  # manifest_version: the escape hatch for future format changes.
  version="$(manifest_get manifest_version)"
  if ! _word_in_list "$version" "$SUPPORTED_MANIFEST_VERSIONS"; then
    echo "ERROR: unsupported manifest_version '$version' in $MANIFEST (this doctor supports: $SUPPORTED_MANIFEST_VERSIONS)" >&2
    exit 2
  fi

  # topology: selects the check catalog, never inferred.
  topology="$(manifest_get topology)"
  if ! _word_in_list "$topology" "$VALID_TOPOLOGIES"; then
    echo "ERROR: unknown topology '$topology' in $MANIFEST (valid: role-clones, embedded, user-tier)" >&2
    exit 2
  fi

  # memory_layout.
  layout="$(manifest_get memory_layout)"
  if ! _word_in_list "$layout" "$VALID_MEMORY_LAYOUTS"; then
    echo "ERROR: unknown memory_layout '$layout' in $MANIFEST (valid: roles, flat)" >&2
    exit 2
  fi

  # adapter values (repeatable, optional).
  while IFS= read -r adapter_value; do
    [ -n "$adapter_value" ] || continue
    if ! _word_in_list "$adapter_value" "$VALID_ADAPTER_VALUES"; then
      echo "ERROR: unknown adapter '$adapter_value' in $MANIFEST (valid: claude-code, codex, opencode, pi)" >&2
      exit 2
    fi
  done < <(manifest_get_all adapter)

  # Per-topology key validity: a key valid only for another topology is an
  # invalid manifest, not a soft warning.
  for k in $EMBEDDED_ONLY_KEYS; do
    if [ -n "$(manifest_get "$k")" ] && [ "$topology" != "embedded" ]; then
      echo "ERROR: key '$k' is only valid for topology=embedded (this manifest declares topology=$topology) in $MANIFEST" >&2
      exit 2
    fi
  done
  for k in $ROLE_CLONES_ONLY_KEYS; do
    if [ -n "$(manifest_get "$k")" ] && [ "$topology" != "role-clones" ]; then
      echo "ERROR: key '$k' is only valid for topology=role-clones (this manifest declares topology=$topology) in $MANIFEST" >&2
      exit 2
    fi
  done

  # skills_mount value (embedded only, already confirmed permitted above).
  v="$(manifest_get skills_mount)"
  if [ -n "$v" ] && ! _word_in_list "$v" "$VALID_SKILLS_MOUNT_VALUES"; then
    echo "ERROR: invalid skills_mount '$v' in $MANIFEST (valid: true, false)" >&2
    exit 2
  fi

  # opencode value (role-clones only, already confirmed permitted above).
  v="$(manifest_get opencode)"
  if [ -n "$v" ] && ! _word_in_list "$v" "$VALID_OPENCODE_VALUES"; then
    echo "ERROR: invalid opencode '$v' in $MANIFEST (valid: global, per-clone)" >&2
    exit 2
  fi

  # claude_hook / codex_hook / pi_extension must be repo-relative paths,
  # not absolute.
  for k in claude_hook codex_hook pi_extension; do
    while IFS= read -r hook; do
      [ -n "$hook" ] || continue
      case "$hook" in
        /*)
          echo "ERROR: $k '$hook' in $MANIFEST must be a repo-relative path, not absolute" >&2
          exit 2
          ;;
      esac
    done < <(manifest_get_all "$k")
  done

  # role_source (optional, consumer-side, claude-personas#49): points a
  # role-clones or embedded instance at the user-scope roles instance.
  # Hard error on user-tier (self-reference: the user-tier instance IS the
  # role tier's home). Must be repo-relative: the committed <role>/user
  # symlinks are derived from it and encode the sibling-layout assumption.
  v="$(manifest_get role_source)"
  if [ -n "$v" ]; then
    if [ "$topology" = "user-tier" ]; then
      echo "ERROR: key 'role_source' is not valid for topology=user-tier (the user-tier instance is the role tier's home, not a consumer of it) in $MANIFEST" >&2
      exit 2
    fi
    case "$v" in
      /*)
        echo "ERROR: role_source '$v' in $MANIFEST must be a repo-relative path, not absolute" >&2
        exit 2
        ;;
    esac
  fi
}

validate_manifest_syntax
validate_manifest_semantics

# --- populate globals for topology check functions (Tasks 2-8) ---

TOPOLOGY="$(manifest_get topology)"
MEMORY_LAYOUT="$(manifest_get memory_layout)"

ADAPTERS=()
while IFS= read -r _v; do
  [ -n "$_v" ] && ADAPTERS+=("$_v")
done < <(manifest_get_all adapter)

CLAUDE_HOOKS=()
while IFS= read -r _v; do
  [ -n "$_v" ] && CLAUDE_HOOKS+=("$_v")
done < <(manifest_get_all claude_hook)

CODEX_HOOKS=()
while IFS= read -r _v; do
  [ -n "$_v" ] && CODEX_HOOKS+=("$_v")
done < <(manifest_get_all codex_hook)

PI_EXTENSIONS=()
while IFS= read -r _v; do
  [ -n "$_v" ] && PI_EXTENSIONS+=("$_v")
done < <(manifest_get_all pi_extension)

SKILLS_MOUNT="$(manifest_get skills_mount)"
[ -n "$SKILLS_MOUNT" ] || SKILLS_MOUNT="false"

OPENCODE_MODE="$(manifest_get opencode)"
[ -n "$OPENCODE_MODE" ] || OPENCODE_MODE="global"

ROLE_SOURCE="$(manifest_get role_source)"
# Trailing slashes would embed a double slash in the derived <role>/user
# symlink text, permanently text-mismatching a clean hand-created link.
# Loop: ${VAR%/} strips exactly one slash per expansion.
while [ "${ROLE_SOURCE%/}" != "$ROLE_SOURCE" ]; do
  ROLE_SOURCE="${ROLE_SOURCE%/}"
done

# --- shared check core (Task 2): counters, reporters, link/payload/hook checks ---

# Single counter driving the final exit code. FIXED lines never touch it: a
# repaired instance still exits 0 and prints the final OK line.
DRIFT_COUNT=0

report_drift() {
  echo "DRIFT: $1"
  DRIFT_COUNT=$((DRIFT_COUNT + 1))
}

report_fixed() {
  echo "FIXED: $1"
}

report_error() {
  echo "ERROR: $1"
  DRIFT_COUNT=$((DRIFT_COUNT + 1))
}

_symlink_would_loop() {
  # _symlink_would_loop <path> <target> - true when a symlink <path> -> <target>
  # resolves back through <path> itself, i.e. the link is (or would be) part
  # of an ELOOP cycle. Follows the target's symlink chain hop by hop,
  # comparing physical identities (resolved parent + basename), so it catches
  # the 1-hop parent-alias loop of #78 (.agents/memory -> ../.agents/memory
  # under .claude -> .agents) as well as leaf cycles (CLAUDE.md -> AGENTS.md
  # -> CLAUDE.md) and mirror-aliased 2-hop cycles. Returns false when the
  # chain leaves <path>'s identity and terminates, or when a parent dir is
  # unresolvable (no claim - the caller's ordinary branches take over).
  # Chain depth is capped; exhausting the cap counts as a loop (conservative:
  # doctor never writes into a chain it cannot see the end of).
  local p="$1" tgt="$2" hops=0
  local p_id cur cur_dir hop_dir hop_id

  cur_dir="$(cd "$(dirname "$p")" 2>/dev/null && pwd -P)" || return 1
  p_id="$cur_dir/$(basename "$p")"
  cur="$tgt"
  while [ "$hops" -lt 8 ]; do
    case "$cur" in
      /*) hop_dir="$(cd "$(dirname "$cur")" 2>/dev/null && pwd -P)" || return 1 ;;
      *)  hop_dir="$(cd "$cur_dir/$(dirname "$cur")" 2>/dev/null && pwd -P)" || return 1 ;;
    esac
    hop_id="$hop_dir/$(basename "$cur")"
    if [ "$hop_id" = "$p_id" ]; then
      return 0
    fi
    if [ -L "$hop_id" ]; then
      cur="$(readlink "$hop_id")" || return 1
      cur_dir="$hop_dir"
      hops=$((hops + 1))
    else
      return 1
    fi
  done
  return 0
}

need_link() {
  # need_link <path> <target> <label>
  #
  # Correct symlink (right target) that resolves: silent, does nothing.
  # Self-referential expectation - <target> resolves back to <path> itself,
  # which happens when two parent dirs alias one physical dir (a consumer
  # canonicalizes on .agents/ and symlinks .claude -> .agents, #78): if
  # <path> resolves anyway the expectation is satisfied transitively through
  # the alias - silent; if it does not resolve, ERROR in both modes. Writing
  # the requested link would ELOOP the mount, and an already-written
  # self-loop must never read as "correct".
  # Real (non-symlink) file or dir at <path>: DRIFT, never touched in either
  # mode - that path is owned by something else.
  # Wrong or missing symlink: --check reports drift; default (fix) mode
  # mkdir -p's the parent then ln -sfn's the target.
  local p="$1" tgt="$2" label="$3"

  if [ -L "$p" ] && [ "$(readlink "$p")" = "$tgt" ] && [ -e "$p" ]; then
    return 0
  fi

  # Only not-plainly-correct states reach the (subshell-heavy) loop walk.
  if _symlink_would_loop "$p" "$tgt"; then
    if [ -e "$p" ]; then
      return 0
    fi
    report_error "$label -> $tgt resolves back to the link itself and nothing resolves there - refusing to write a self-referential symlink (aliased parent dirs?)"
    return 0
  fi

  if [ -e "$p" ] && [ ! -L "$p" ]; then
    report_drift "$label exists and is not a symlink (refusing to touch)"
    return 0
  fi

  # Correct link text that dangles without looping (target not created yet):
  # accepted, matching the pre-#78 contract - the missing target is some
  # other check's drift to report.
  if [ -L "$p" ] && [ "$(readlink "$p")" = "$tgt" ]; then
    return 0
  fi

  if [ "$CHECK" = 1 ]; then
    report_drift "$label -> $(readlink "$p" 2>/dev/null || echo MISSING), expected $tgt"
  elif mkdir -p "$(dirname "$p")" 2>/dev/null && ln -sfn "$tgt" "$p" 2>/dev/null; then
    report_fixed "$label -> $tgt"
  else
    report_error "could not create $label -> $tgt"
  fi
}

same_physical_dir() {
  # same_physical_dir <a> <b> - true when both exist and are one physical
  # file/dir (device+inode, symlinks followed); false when either is
  # missing. Detects the aliased layout where a consumer canonicalizes on
  # .agents/ and symlinks .claude -> .agents (one dir, two names - see #78).
  [ "$1" -ef "$2" ]
}

is_reserved_name() {
  # is_reserved_name <name> - true when <name> is a reserved non-role dir
  # name, folded to lowercase: on a case-insensitive filesystem (macOS APFS
  # default) Examples/ IS examples/. THE reserved-name set for this file;
  # the standalone payload copies (list-roles.sh, init-clone.sh,
  # inject-subagent-role-pointer.sh) inline the same case arm because the
  # hook may not source a lib at runtime - test_framework_files.sh greps
  # all four and fails on any desync (#76).
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    shared|examples) return 0 ;;
  esac
  return 1
}

claude_aliases_agents() {
  # claude_aliases_agents <dir> - true when <dir>/.claude is an alias of
  # <dir>/.agents: either both resolve to one physical dir, or .claude is a
  # committed '.claude -> .agents' symlink that merely dangles because
  # .agents/ is not materialized yet (fresh clone). On an aliased workspace
  # the .claude/memory hop has no existence of its own - it is satisfied
  # transitively by the .agents/memory mount, and must never be written.
  same_physical_dir "$1/.claude" "$1/.agents" && return 0
  [ -L "$1/.claude" ] && [ "$(readlink "$1/.claude")" = ".agents" ]
}

require_jq() {
  # require_jq <what-for>
  # jq present: silent, returns 0. jq absent: one DRIFT line naming what the
  # skipped checks were for, returns 1 - callers skip their jq-dependent
  # checks loudly instead of silently swallowing them.
  if command -v jq >/dev/null 2>&1; then
    return 0
  fi
  report_drift "jq not installed (needed for $1) - skipping those checks"
  return 1
}

check_payload() {
  # Payload sanity, keyed off the declared memory_layout. flat: a single
  # always-loaded index. roles: every role dir (same discovery rule as
  # list-roles.sh / init-clone.sh - a dir with MEMORY.md, excluding shared
  # and examples) plus shared/MEMORY.md.
  case "$MEMORY_LAYOUT" in
    flat)
      [ -f "$ROOT/.agents/memory/MEMORY.md" ] \
        || report_drift ".agents/memory/MEMORY.md missing"
      ;;
    roles)
      local d n role_count=0
      for d in "$ROOT"/*/; do
        [ -d "$d" ] || continue
        n="$(basename "$d")"
        if [ -f "$d/MEMORY.md" ] && ! is_reserved_name "$n"; then
          role_count=$((role_count + 1))
        fi
      done
      if [ "$role_count" -eq 0 ]; then
        report_drift "roles layout declared but no role dirs found"
      fi
      [ -f "$ROOT/shared/MEMORY.md" ] \
        || report_drift "shared/MEMORY.md missing"
      ;;
  esac
}

check_hook_scripts() {
  # Every declared claude_hook / codex_hook must exist and be executable at
  # its repo-relative path under $ROOT. The two failure modes get distinct
  # DRIFT lines: "missing" points at a wrong path or an undeployed script,
  # "not executable" at a chmod problem - different fixes.
  local hook

  _check_one_hook() { # $1=manifest key  $2=repo-relative hook path
    if [ ! -e "$ROOT/$2" ]; then
      report_drift "$1 '$2' missing at $ROOT/$2"
    elif [ ! -x "$ROOT/$2" ]; then
      report_drift "$1 '$2' not executable at $ROOT/$2 (chmod +x it)"
    fi
  }

  if [ "${#CLAUDE_HOOKS[@]}" -gt 0 ]; then
    for hook in "${CLAUDE_HOOKS[@]}"; do
      _check_one_hook claude_hook "$hook"
    done
  fi

  if [ "${#CODEX_HOOKS[@]}" -gt 0 ]; then
    for hook in "${CODEX_HOOKS[@]}"; do
      _check_one_hook codex_hook "$hook"
    done
  fi
}

check_framework_staleness() {
  # Staleness of the installed framework payload vs its pinned source
  # (spec section 3). Being BEHIND is INFO (wiring is intact; an update is
  # available); a pin the source cannot resolve, or an unreachable source,
  # is DRIFT (the recorded provenance is broken). Read-only, best effort:
  # no framework_ref key means not installed via install.sh - silent.
  local pin src parent n
  pin="$(manifest_get framework_ref)"
  [ -n "$pin" ] || return 0
  src="$(manifest_get framework_source)"
  if [ -n "$src" ]; then
    case "$src" in
      /*) ;;
      *) src="$ROOT/$src" ;;
    esac
  else
    parent="$(dirname "$ROOT")"
    if [ -f "$parent/agent-personas/framework/FILES" ]; then
      src="$parent/agent-personas"
    elif [ -f "$parent/claude-personas/framework/FILES" ]; then
      src="$parent/claude-personas"
    else
      report_drift "framework_ref is pinned but no framework_source is set and no sibling framework clone exists - set framework_source in the manifest"
      return 0
    fi
  fi
  if [ ! -d "$src" ]; then
    report_drift "framework_source '$src' unreachable"
    return 0
  fi
  if ! git -C "$src" rev-parse --verify --quiet "$pin^{commit}" >/dev/null 2>&1; then
    report_drift "framework_ref '$pin' not found in source $src - fetch the source or fix the pin"
    return 0
  fi
  n="$(git -C "$src" rev-list --count "$pin..HEAD" 2>/dev/null || echo 0)"
  if [ "$n" -gt 0 ]; then
    echo "INFO: framework payload $n commit(s) behind pinned source $src (run install.sh --sync)"
  fi
}

# --- topology dispatch (stubs; catalogs land in later tasks) ---

_role_clones_find_workspace() {
  # _role_clones_find_workspace <root_abs> <parent> <memrepo_name>
  #                              <project_name-or-empty> <role>
  #
  # Candidate walk in list-roles.sh order: the memory repo itself (self-mount
  # candidate), then the no-suffix clone, then the suffixed clone (the last
  # two are only tried when project_name is non-empty - the naming-convention
  # DRIFT already fired once for the whole instance if it's empty). A
  # candidate claims the role when it has .git AND either its .agents/memory
  # (or, v3.1 fallback, its .claude/memory) symlink targets end in "/<role>"
  # or equal "<role>" outright, or - a broken-rewire fallback, matching
  # list-roles.sh - its own path ends in "-<role>".
  #
  # Exhaustive (Task 7): every claiming candidate is printed, one per line, in
  # walk order - this function no longer stops at the first match. The caller
  # (_role_clones_check_role) decides what more than one claimant means (the
  # multi-candidate DRIFT) and which claimant gets the per-workspace checks
  # (the first line - walk order doubles as precedence order). Candidates are
  # distinct by construction (memory repo, no-suffix, suffixed paths differ),
  # but a pwd -P dedup guards against double-counting the same physical dir
  # under two different candidate spellings.
  local root_abs="$1" parent="$2" memrepo_name="$3" project_name="$4" role="$5"
  local candidates cand link target claims phys seen_phys=""

  candidates=("$root_abs")
  if [ -n "$project_name" ]; then
    candidates+=("$parent/$project_name" "$parent/$project_name-$role")
  fi

  for cand in "${candidates[@]}"; do
    [ -d "$cand/.git" ] || continue

    link=""
    if [ -L "$cand/.agents/memory" ]; then
      link="$cand/.agents/memory"
    elif [ -L "$cand/.claude/memory" ]; then
      link="$cand/.claude/memory"
    else
      continue
    fi

    target="$(readlink "$link")"
    claims=0
    case "$target" in
      *"/$role"|"$role") claims=1 ;;
    esac
    if [ "$claims" = 0 ]; then
      case "$cand" in
        *"-$role") claims=1 ;;
      esac
    fi
    [ "$claims" = 1 ] || continue

    phys="$(cd "$cand" 2>/dev/null && pwd -P)"
    case " $seen_phys " in
      *" $phys "*) continue ;;
    esac
    seen_phys="$seen_phys $phys"

    printf '%s\n' "$cand"
  done
}

_role_clones_check_exclude() {
  # _role_clones_check_exclude <workspace> <line>...
  # .git/info/exclude carries the init-clone-owned lines, append-only:
  # missing is DRIFT in --check, appended (never a rewrite) in fix mode.
  local workspace="$1"
  shift
  local exclude="$workspace/.git/info/exclude" line

  for line in "$@"; do
    if [ -f "$exclude" ] && grep -qxF -- "$line" "$exclude" 2>/dev/null; then
      continue
    fi

    if [ "$CHECK" = 1 ]; then
      report_drift "$exclude missing '$line'"
    elif mkdir -p "$(dirname "$exclude")" 2>/dev/null && touch "$exclude" 2>/dev/null && printf '%s\n' "$line" >> "$exclude" 2>/dev/null; then
      report_fixed "$exclude appended '$line'"
    else
      report_error "could not append '$line' to $exclude"
    fi
  done
}

_role_clones_regen_codex_hooks_json() {
  # _role_clones_regen_codex_hooks_json <memrepo_logical> <workspace> <role>
  # Regenerate <workspace>/.codex/hooks.json wholesale, matching
  # init-clone.sh's wire_codex_adapter shape exactly: one SessionStart hook
  # calling THIS memory repo's inject-role-index.sh with THIS role dir,
  # timeout 10, the fixed statusMessage. <memrepo_logical> must be the LOGICAL
  # (plain `pwd`, not `pwd -P`) memory-repo path - init-clone.sh's
  # wire_codex_adapter embeds $MEMORY_REPO="$(pwd)" verbatim, unlike its
  # external-hop/opencode siblings which resolve via pwd -P; matching that
  # exactly (not the canonical root_abs used elsewhere in this file) is what
  # keeps this check from false-DRIFTing a freshly-init-clone.sh-wired
  # workspace whenever a path component (e.g. macOS's /var) is itself a
  # symlink.
  local memrepo_logical="$1" workspace="$2" role="$3" out tmp_json cmd_value
  out="$workspace/.codex/hooks.json"
  # Same embed-safety guard as init-clone.sh's wire_codex_adapter: no escaper
  # here (jq dependency deliberately avoided), so a quote or backslash would
  # silently produce invalid JSON and an apostrophe would break the
  # single-quoted shell command string. Refuse rather than write a corrupt
  # file that FIXED-and-exit-0 would misreport as repaired.
  case "$memrepo_logical$role" in (*[\"\\\']*)
    report_error "$out not regenerated: memory-repo path contains a quote or backslash - cannot embed safely in hooks.json; wire it by hand (init-clone.sh refuses the same path)"
    return 0 ;;
  esac
  # Same missing-payload guard as init-clone.sh's wire_codex_adapter: never
  # wire a hook to a script that is not there - regenerating would convert a
  # possibly-working hooks.json into a dangling one and report it FIXED.
  if [ ! -x "$memrepo_logical/.agents/hooks/lib/inject-role-index.sh" ]; then
    report_error "$out not regenerated: $memrepo_logical/.agents/hooks/lib/inject-role-index.sh missing or not executable - install the framework payload first (copy framework/hooks/inject-role-index.sh to .agents/hooks/lib/ in the memory repo)"
    return 0
  fi
  cmd_value="'$memrepo_logical/.agents/hooks/lib/inject-role-index.sh' '$memrepo_logical/$role'"
  tmp_json="$(mktemp 2>/dev/null)"
  if [ -z "$tmp_json" ]; then
    report_error "could not create temp file for $out regeneration"
    return 0
  fi

  {
    printf '{\n  "hooks": {\n    "SessionStart": [\n      {\n        "hooks": [\n          {\n'
    printf '            "type": "command",\n'
    printf '            "command": "%s",\n' "$cmd_value"
    printf '            "timeout": 10,\n'
    printf '            "statusMessage": "Injecting role memory index…"\n'
    printf '          }\n        ]\n      }\n    ]\n  }\n}\n'
  } > "$tmp_json"

  if mkdir -p "$workspace/.codex" 2>/dev/null && mv "$tmp_json" "$out" 2>/dev/null; then
    report_fixed "$out regenerated for role $role"
    _role_clones_check_exclude "$workspace" "/.codex/hooks.json"
  else
    rm -f "$tmp_json"
    report_error "could not regenerate $out"
  fi
}

_role_clones_check_codex_hooks_json() {
  # _role_clones_check_codex_hooks_json <memrepo_logical> <workspace> <role>
  # Per-workspace .codex/hooks.json: the single SessionStart command must be
  # exactly '<memrepo_logical>/.agents/hooks/lib/inject-role-index.sh'
  # '<memrepo_logical>/<role>' - grep -qxF whole-line exact match, never
  # substring (a copied-from-elsewhere hooks.json with a plausible shape but
  # another machine's absolute prefix must still be named DRIFT). Missing is
  # DRIFT too - init-clone.sh would have generated this file; fix mode
  # regenerates it wholesale (note: Codex /hooks re-approval will be needed
  # after either fix). <memrepo_logical> is the LOGICAL memory-repo path (see
  # the regen function's comment on why - it must match init-clone.sh's own
  # $(pwd)-based MEMORY_REPO, not this file's usual canonical root_abs).
  local memrepo_logical="$1" workspace="$2" role="$3"
  if ! require_jq "codex hooks.json checks (role $role)"; then
    return 0
  fi

  local hooks="$workspace/.codex/hooks.json" cmds expected inject_script
  inject_script="$memrepo_logical/.agents/hooks/lib/inject-role-index.sh"
  expected="'$inject_script' '$memrepo_logical/$role'"
  if [ -f "$hooks" ]; then
    cmds="$(jq -r '.hooks.SessionStart[]?.hooks[]?.command' "$hooks" 2>/dev/null)"
  else
    cmds=""
  fi

  if printf '%s\n' "$cmds" | grep -qxF -- "$expected"; then
    # The wired string is only as good as its target: a matching command
    # pointing at a missing/non-executable script is a dead hook, not a pass
    # (the target used to be a tracked template file; post-reshuffle it is an
    # installed copy whose presence must be verified).
    if [ -x "$inject_script" ]; then
      return 0
    fi
    report_drift "$hooks wires role $role but $inject_script is missing or not executable - install the framework payload (copy framework/hooks/inject-role-index.sh to .agents/hooks/lib/ in the memory repo)"
    return 0
  fi

  if [ "$CHECK" = 1 ]; then
    if [ -f "$hooks" ]; then
      report_drift "$hooks does not exactly wire role $role's inject-role-index.sh for this memory repo ($memrepo_logical)"
    else
      report_drift "$hooks missing for role $role (regenerable; Codex /hooks re-approval will be needed after fix)"
    fi
  else
    _role_clones_regen_codex_hooks_json "$memrepo_logical" "$workspace" "$role"
  fi
}

_role_clones_regen_opencode_per_clone() {
  # _role_clones_regen_opencode_per_clone <workspace> <role>
  local workspace="$1" role="$2" oc
  oc="$workspace/opencode.json"
  # Embed-safety guard matching init-clone.sh's wire_opencode_adapter: the
  # path lands inside a JSON string only, so just quote and backslash are
  # unsafe (an apostrophe is fine here, unlike the codex hooks.json case).
  case "$workspace" in (*[\"\\]*)
    report_error "$oc not regenerated: clone path contains a quote or backslash - cannot embed safely in opencode.json; wire it by hand (init-clone.sh refuses the same path)"
    return 0 ;;
  esac
  if printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "instructions": ["%s"]\n}\n' "$workspace/.agents/memory/MEMORY.md" > "$oc"; then
    report_fixed "$oc regenerated for role $role"
    _role_clones_check_exclude "$workspace" "/opencode.json"
  else
    report_error "could not regenerate $oc"
  fi
}

_role_clones_check_opencode_per_clone() {
  # _role_clones_check_opencode_per_clone <workspace> <role>
  # opencode=per-clone: the generated opencode.json's instructions[0] must
  # equal <workspace>/.agents/memory/MEMORY.md exactly (jq-extracted); wrong
  # or missing is regenerable, matching init-clone.sh's wire_opencode_adapter
  # shape ($schema + instructions) exactly.
  local workspace="$1" role="$2"
  if ! require_jq "opencode.json checks (role $role)"; then
    return 0
  fi

  local oc="$workspace/opencode.json" expected got
  expected="$workspace/.agents/memory/MEMORY.md"
  got="$(jq -r '.instructions[0]? // empty' "$oc" 2>/dev/null)"

  if [ "$got" = "$expected" ]; then
    return 0
  fi

  if [ "$CHECK" = 1 ]; then
    report_drift "$oc instructions[0] is not \"$expected\" for role $role (regenerable)"
  else
    _role_clones_regen_opencode_per_clone "$workspace" "$role"
  fi
}

_role_clones_check_opencode_global() {
  # Single global check for the WHOLE run (not per workspace): the
  # machine-wide ~/.config/opencode/opencode.json instructions array must
  # contain the RELATIVE entry ".agents/memory/MEMORY.md" - report-only, this
  # file is user-owned (serves every clone via OpenCode's per-session project
  # dir resolution), doctor.sh only names the exact line to add.
  if ! require_jq "opencode.json checks"; then
    return 0
  fi

  local oc="$HOME/.config/opencode/opencode.json"
  if ! jq -e '.instructions | index(".agents/memory/MEMORY.md")' "$oc" >/dev/null 2>&1; then
    report_drift "$oc missing or its instructions lack \".agents/memory/MEMORY.md\" - add it to the instructions array"
  fi
}

_role_clones_check_role() {
  # _role_clones_check_role <root_abs> <parent> <memrepo_name>
  #                          <project_name-or-empty> <role> <memrepo_logical>
  # <memrepo_logical> (plain `pwd`, not `pwd -P`) is only for the codex
  # hooks.json check - see its comment for why it must differ from root_abs.
  local root_abs="$1" parent="$2" memrepo_name="$3" project_name="$4" role="$5" memrepo_logical="$6"
  local workspaces workspace expected_mount lines _w

  workspaces=()
  while IFS= read -r _w; do
    [ -n "$_w" ] && workspaces+=("$_w")
  done < <(_role_clones_find_workspace "$root_abs" "$parent" "$memrepo_name" "$project_name" "$role")

  if [ "${#workspaces[@]}" -eq 0 ]; then
    echo "INFO: role $role - no workspace wired"
    return 0
  fi

  if [ "${#workspaces[@]}" -gt 1 ]; then
    # Multi-candidate flag (Task 7, PR #40 review): more than one workspace
    # claiming the same role is DRIFT, report-only in both modes - retiring a
    # workspace is a human decision, doctor.sh never auto-picks a winner. One
    # line names every claimant.
    report_drift "role $role claimed by more than one workspace: ${workspaces[*]} - retire or re-wire one (doctor will not pick)"
  fi

  # Per-workspace checks (mount/exclude/vendor wiring below) run on the FIRST
  # claimant only, regardless of how many claim the role. Walk order is
  # precedence order (matches list-roles.sh semantics), so the real,
  # first-claimant's drifts stay visible even in a multi-candidate state; a
  # stale/duplicate claimant is surfaced solely via the DRIFT above, never
  # double-checked.
  workspace="${workspaces[0]}"

  # Self-mount (workspace IS the memory repo) resolves ../<role> against
  # .agents/; a clone resolves ../../<memrepo>/<role> the same way - matching
  # init-clone.sh's MOUNT_TARGET for --self vs. clone mode exactly.
  if [ "$workspace" = "$root_abs" ]; then
    expected_mount="../$role"
  else
    expected_mount="../../$memrepo_name/$role"
  fi

  need_link "$workspace/.agents/memory" "$expected_mount" "$workspace/.agents/memory"
  # When .claude is an alias of .agents (the workspace canonicalized on the
  # vendor-neutral dir and symlinked .claude -> .agents), .claude/memory IS
  # .agents/memory: the hop is satisfied transitively by the mount above,
  # and writing ../.agents/memory onto the shared inode would replace that
  # mount with a self-loop (#78). Supported layout - skip, don't clobber.
  # The '/.claude/memory' exclude line is skipped for the same reason: on an
  # aliased clone that path never exists as its own git entry.
  lines=("/.agents/memory")
  if ! claude_aliases_agents "$workspace"; then
    need_link "$workspace/.claude/memory" "../.agents/memory" "$workspace/.claude/memory"
    lines+=("/.claude/memory")
  fi
  if [ -f "$workspace/.codex/hooks.json" ]; then
    lines+=("/.codex/hooks.json")
  fi
  if [ -f "$workspace/opencode.json" ]; then
    lines+=("/opencode.json")
  fi
  _role_clones_check_exclude "$workspace" "${lines[@]}"

  # Vendor wiring (Task 6), gated per-adapter declaration; a claimed
  # workspace only (the INFO "no workspace wired" case already returned).
  local a
  if [ "${#ADAPTERS[@]}" -gt 0 ]; then
    for a in "${ADAPTERS[@]}"; do
      case "$a" in
        claude-code)
          _check_external_cc_hop "$workspace" "$workspace/.claude/memory" "external CC hop for role $role"
          ;;
        codex)
          _role_clones_check_codex_hooks_json "$memrepo_logical" "$workspace" "$role"
          ;;
        opencode)
          if [ "$OPENCODE_MODE" = "per-clone" ]; then
            _role_clones_check_opencode_per_clone "$workspace" "$role"
          fi
          # global mode is a single machine-wide check, run once from
          # topology_role_clones_checks - not per workspace.
          ;;
      esac
    done
  fi
}

topology_role_clones_checks() {
  # Role-clone constellation, doctored FROM the memory repo: role discovery,
  # the candidate walk, the multi-candidate flag, per-workspace mount/exclude
  # checks, and per-workspace vendor wiring (external CC hop, codex
  # hooks.json, opencode). The orphan sweep is Task 8.
  local root_abs parent memrepo_name project_name memrepo_logical

  root_abs="$(cd "$ROOT" && pwd -P)"
  parent="$(dirname "$root_abs")"
  memrepo_name="$(basename "$root_abs")"
  # Logical (non-canonicalized) memory-repo path - matches init-clone.sh's
  # own $(pwd) convention for the codex hooks.json check (see that check's
  # comment); everything else in this function stays on the canonical
  # root_abs, which is what the workspace path / relative-target comparisons
  # already rely on.
  memrepo_logical="$(cd "$ROOT" && pwd)"

  case "$memrepo_name" in
    claude-personas-*)
      project_name="${memrepo_name#claude-personas-}"
      ;;
    *)
      report_drift "memory repo dir name '$memrepo_name' does not start with 'claude-personas-' - cannot derive the project name for the clone candidate walk (rename the memory repo to claude-personas-<project>, matching list-roles.sh's naming convention)"
      project_name=""
      ;;
  esac

  # Role discovery: same rule as check_payload / list-roles.sh / init-clone.sh
  # - a dir with MEMORY.md at the root, excluding shared and examples.
  local roles d n
  roles=()
  for d in "$root_abs"/*/; do
    [ -d "$d" ] || continue
    n="$(basename "$d")"
    if [ -f "$d/MEMORY.md" ] && ! is_reserved_name "$n"; then
      roles+=("$n")
    fi
  done

  if [ "${#roles[@]}" -gt 0 ]; then
    local role
    for role in "${roles[@]}"; do
      _role_clones_check_role "$root_abs" "$parent" "$memrepo_name" "$project_name" "$role" "$memrepo_logical"
    done
  fi

  # External-hop orphan sweep (Task 8): AFTER every per-workspace hop
  # check/fix above, so a hop this run just repaired is live by sweep time -
  # never a self-inflicted orphan report. Gated on claude-code being
  # declared (the only adapter that creates external hops).
  local a
  if [ "${#ADAPTERS[@]}" -gt 0 ]; then
    for a in "${ADAPTERS[@]}"; do
      if [ "$a" = "claude-code" ]; then
        _sweep_orphan_external_hops
        break
      fi
    done
  fi

  # OpenCode global mode: one machine-wide check for the whole run, gated on
  # the opencode adapter being declared at all.
  local a
  if [ "${#ADAPTERS[@]}" -gt 0 ] && [ "$OPENCODE_MODE" = "global" ]; then
    for a in "${ADAPTERS[@]}"; do
      if [ "$a" = "opencode" ]; then
        _role_clones_check_opencode_global
        break
      fi
    done
  fi
}

_embedded_check_claude_settings_hooks() {
  # Every declared claude_hook must be wired in .claude/settings.json via the
  # exact "$CLAUDE_PROJECT_DIR/<hook>" command string - including the
  # embedded literal double quotes, which is what Claude Code itself stores
  # (see cerebrum's .claude/settings.json). Report-only: doctor.sh never
  # rewrites a hand-authored settings.json.
  if ! require_jq "settings.json hook checks"; then
    return 0
  fi
  if [ "${#CLAUDE_HOOKS[@]}" -eq 0 ]; then
    return 0
  fi

  local cmds hook expected
  cmds="$(jq -r '.hooks.SessionStart[]?.hooks[]?.command' "$ROOT/.claude/settings.json" 2>/dev/null)"
  for hook in "${CLAUDE_HOOKS[@]}"; do
    expected="$(printf '"$CLAUDE_PROJECT_DIR/%s"' "$hook")"
    if ! printf '%s\n' "$cmds" | grep -qxF -- "$expected"; then
      report_drift ".claude/settings.json does not wire claude_hook '$hook' via \$CLAUDE_PROJECT_DIR"
    fi
  done
}

_check_external_cc_hop() {
  # _check_external_cc_hop <workspace_abs> <expected_target> <label>
  #
  # External Claude Code auto-memory hop for ANY workspace (an embedded
  # instance's root, or a role-clone constellation workspace):
  # $HOME/.claude/projects/<slug>/memory, where <slug> is the workspace's
  # absolute (symlink-resolved) path with '/' and '.' replaced by '-' (matches
  # Claude Code's own project-dir naming, and test_helpers.sh's compute_hash).
  # Load-bearing: without it, Claude Code materializes a REAL directory there
  # and memory silently diverges.
  #
  # A hop resolving (via pwd -P) to <expected_target>'s own canonical
  # resolution is OK whatever its literal link text; a wrong symlink is
  # repaired to <expected_target> via need_link; a real directory is DRIFT,
  # report-only (reconcile by hand); missing is DRIFT in --check, created in
  # fix mode.
  local workspace_abs="$1" expected_target="$2" label="$3"
  local slug ext canonical_ext canonical_expected

  slug="$(printf '%s' "$workspace_abs" | tr '/.' '-')"
  ext="$HOME/.claude/projects/$slug/memory"
  canonical_expected="$(cd "$expected_target" 2>/dev/null && pwd -P)"

  if [ -e "$ext" ] || [ -L "$ext" ]; then
    canonical_ext="$(cd "$ext" 2>/dev/null && pwd -P)"
    if [ -n "$canonical_ext" ] && [ "$canonical_ext" = "$canonical_expected" ]; then
      return 0
    elif [ -L "$ext" ]; then
      need_link "$ext" "$expected_target" "$label"
    else
      report_drift "$ext is a real directory - Claude Code may have written memories there; reconcile by hand"
    fi
  elif [ "$CHECK" = 1 ]; then
    report_drift "$label missing ($ext)"
  elif mkdir -p "$(dirname "$ext")" 2>/dev/null && ln -s "$expected_target" "$ext" 2>/dev/null; then
    report_fixed "$ext -> $expected_target"
  else
    report_error "could not create $ext"
  fi
}

_sweep_orphan_external_hops() {
  # External-hop orphan sweep (Task 8, from #34's hand-off): moving or
  # deleting a wired clone/embedded instance leaves its old
  # $HOME/.claude/projects/<old-slug>/memory symlink dangling - a target that
  # no longer exists serves nobody by definition (spec: "External-hop orphan
  # sweep" bullet + the safety-argument paragraph after it). Scans EVERY slug
  # under $HOME/.claude/projects, not just this instance's own - the projects
  # dir is global - but the only fix action is removing a symlink whose
  # target is gone, so a live symlink (whatever it points at, possibly
  # another instance entirely) and a real file or directory are never
  # touched. The slug directory itself is never removed even when this
  # empties it out - other Claude Code session data may live there, so the
  # sweep stays surgical to the memory symlink only.
  #
  # Called for BOTH role-clones and embedded topologies, after each
  # topology's own per-workspace hop checks/fixes, so a hop this run just
  # repaired is already live by sweep time (no self-inflicted orphan
  # report in fix mode).
  local projects_dir="$HOME/.claude/projects" p target

  [ -d "$projects_dir" ] || return 0

  for p in "$projects_dir"/*/memory; do
    [ -L "$p" ] || continue
    [ ! -e "$p" ] || continue

    target="$(readlink "$p")"
    if [ -L "$target" ] || [ -e "$target" ]; then
      # The hop's immediate target is still on disk - the clone exists but
      # its mount chain does not resolve (e.g. a self-looped mount, #78's
      # aftermath). Reaping would erase the last pointer to the broken
      # clone, so this is DRIFT in both modes, never a removal.
      report_drift "external hop $p -> $target does not resolve but the target still exists (broken mount chain, not a moved clone) - repair the clone's mount; doctor will not reap"
      continue
    fi
    if [ "$CHECK" = 1 ]; then
      report_drift "orphan external hop $p -> $target (target gone - moved or deleted clone)"
    elif rm -f "$p" 2>/dev/null; then
      report_fixed "removed orphan external hop $p"
    else
      report_error "could not remove orphan external hop $p"
    fi
  done
}

_embedded_check_external_cc_hop() {
  local root_abs
  root_abs="$(cd "$ROOT" && pwd -P)"
  _check_external_cc_hop "$root_abs" "$root_abs/.claude/memory" "external CC auto-memory symlink"
}

_embedded_regen_codex_hooks_json() {
  # Regenerate .codex/hooks.json wholesale for THIS root: one hooks-array
  # entry per declared codex_hook, in manifest order, matching the JSON
  # shape cerebrum's sync.sh writes (single SessionStart entry, "timeout":
  # 10, statusMessage derived from the hook's basename).
  local root_abs="$1" out tmp_json i n hook base
  out="$ROOT/.codex/hooks.json"
  # Embed-safety guard (same class as init-clone.sh's wire_codex_adapter): the
  # instance path and every declared codex_hook land inside a single-quoted
  # shell command string within JSON - a quote or backslash breaks the JSON,
  # an apostrophe breaks the quoting. Refuse rather than write a corrupt file.
  case "$root_abs${CODEX_HOOKS[*]:-}" in (*[\"\\\']*)
    report_error "$out not regenerated: instance path or a codex_hook contains a quote or backslash - cannot embed safely in hooks.json; wire it by hand"
    return 0 ;;
  esac
  tmp_json="$(mktemp 2>/dev/null)"
  if [ -z "$tmp_json" ]; then
    report_error "could not create temp file for .codex/hooks.json regeneration"
    return 0
  fi

  {
    printf '{\n  "hooks": {\n    "SessionStart": [\n      {\n        "hooks": [\n'
    n="${#CODEX_HOOKS[@]}"
    i=0
    for hook in "${CODEX_HOOKS[@]}"; do
      i=$((i + 1))
      base="$(basename "$hook")"
      printf '          {\n'
      printf '            "type": "command",\n'
      printf '            "command": "'"'"'%s/%s'"'"'",\n' "$root_abs" "$hook"
      printf '            "timeout": 10,\n'
      printf '            "statusMessage": "Running %s…"\n' "$base"
      if [ "$i" -lt "$n" ]; then
        printf '          },\n'
      else
        printf '          }\n'
      fi
    done
    printf '        ]\n      }\n    ]\n  }\n}\n'
  } > "$tmp_json"

  if mkdir -p "$ROOT/.codex" 2>/dev/null && mv "$tmp_json" "$out" 2>/dev/null; then
    report_fixed ".codex/hooks.json regenerated for $root_abs"
  else
    rm -f "$tmp_json"
    report_error "could not regenerate .codex/hooks.json"
  fi
}

_embedded_check_codex_hooks_json() {
  # .codex/hooks.json must wire every declared codex_hook as an absolute,
  # single-quoted, exact-match command string rooted at THIS instance's path
  # - grep -qxF (whole-line exact match), never a substring check, which
  # would wrongly accept another machine's absolute prefix as long as the
  # hook's relative suffix happened to appear somewhere in the file.
  if ! require_jq "hooks.json checks"; then
    return 0
  fi
  if [ "${#CODEX_HOOKS[@]}" -eq 0 ]; then
    return 0
  fi

  local root_abs cmds hook expected codex_ok=1
  root_abs="$(cd "$ROOT" && pwd -P)"
  if [ -f "$ROOT/.codex/hooks.json" ]; then
    cmds="$(jq -r '.hooks.SessionStart[]?.hooks[]?.command' "$ROOT/.codex/hooks.json" 2>/dev/null)"
  else
    cmds=""
  fi
  for hook in "${CODEX_HOOKS[@]}"; do
    expected="'$root_abs/$hook'"
    if ! printf '%s\n' "$cmds" | grep -qxF -- "$expected"; then
      codex_ok=0
    fi
  done

  if [ "$codex_ok" = 1 ]; then
    return 0
  fi

  if [ "$CHECK" = 1 ]; then
    report_drift ".codex/hooks.json does not wire all declared codex_hook entries for this root ($root_abs)"
  else
    _embedded_regen_codex_hooks_json "$root_abs"
  fi
}

_embedded_check_pi_extensions() {
  # pi discovers project extensions only under .pi/extensions/ (trust-gated),
  # while the installed payload lives under .agents/ (install.sh refuses
  # landings outside it). Bridge: each declared pi_extension module gets a
  # one-line re-export shim at .pi/extensions/<basename>. The shim is fully
  # derivable from the manifest, so fix mode regenerates it wholesale (same
  # policy as .codex/hooks.json); the payload module itself is installer-owned
  # - a missing module is report-only, and no shim is generated over it (a
  # dangling re-export would trade a visible gap for a load error).
  if [ "${#PI_EXTENSIONS[@]}" -eq 0 ]; then
    return 0
  fi

  # Shim filenames derive from the module basename, so two declared modules
  # differing only in directory would silently claim (and overwrite) the same
  # shim. Refuse the colliding entries up front; newline list + grep -qxF so
  # a basename containing spaces cannot split the match.
  local mod shim_rel shim expected dup_basenames
  dup_basenames="$(for mod in "${PI_EXTENSIONS[@]}"; do basename "$mod"; done | sort | uniq -d)"

  for mod in "${PI_EXTENSIONS[@]}"; do
    if [ ! -f "$ROOT/$mod" ]; then
      report_drift "pi_extension '$mod' missing at $ROOT/$mod - run install.sh --sync (or fix the manifest path)"
      continue
    fi
    if [ -n "$dup_basenames" ] \
      && printf '%s\n' "$dup_basenames" | grep -qxF -- "$(basename "$mod")"; then
      report_error "pi_extension '$mod': its basename collides with another declared pi_extension - both would land at .pi/extensions/$(basename "$mod"); rename one module"
      continue
    fi
    # Same embed-safety guard as the codex/opencode generators: the module
    # path is embedded inside a double-quoted import specifier, and this
    # script ships no escaper - refuse rather than emit a corrupted shim.
    case "$mod" in
      *'"'* | *'\'*)
        report_error "pi_extension '$mod' contains a quote or backslash - cannot embed safely in the generated .pi/extensions shim; rename the module"
        continue
        ;;
    esac
    shim_rel=".pi/extensions/$(basename "$mod")"
    shim="$ROOT/$shim_rel"
    expected="// Generated by doctor.sh (personas pi adapter) - do not edit; fix mode
// regenerates it. Loads the installed framework payload; pi only discovers
// project extensions under .pi/extensions/ (after the project-trust grant).
export { default } from \"../../$mod\";"
    if [ -f "$shim" ] && [ "$(cat "$shim")" = "$expected" ]; then
      continue
    fi
    if [ "$CHECK" = 1 ]; then
      report_drift "$shim_rel missing or not the generated re-export of pi_extension '$mod'"
    elif [ -e "$shim" ] && [ ! -f "$shim" ]; then
      # Same refusal posture as the link checks: never replace a directory
      # or other non-file sitting where the generated shim belongs.
      report_error "$shim_rel exists but is not a regular file - not overwriting"
    elif mkdir -p "$ROOT/.pi/extensions" 2>/dev/null \
      && printf '%s\n' "$expected" > "$shim" 2>/dev/null; then
      report_fixed "$shim_rel -> re-exports $mod"
    else
      report_error "$shim_rel could not be written"
    fi
  done
}

_embedded_check_opencode_instructions() {
  # Root opencode.json's instructions array must contain the flat memory
  # index path. Report-only: doctor.sh never rewrites a hand-authored
  # opencode.json, only names the exact line to add.
  if ! require_jq "opencode.json checks"; then
    return 0
  fi
  if ! jq -e '.instructions | index(".agents/memory/MEMORY.md")' "$ROOT/opencode.json" >/dev/null 2>&1; then
    report_drift "opencode.json missing or its instructions lack \".agents/memory/MEMORY.md\" - add it to the instructions array"
  fi
}

topology_embedded_checks() {
  # In-repo links: fixable regardless of which adapters are declared.
  need_link "$ROOT/.claude/memory" "../.agents/memory" ".claude/memory"
  need_link "$ROOT/CLAUDE.md" "AGENTS.md" "CLAUDE.md"
  if [ "$SKILLS_MOUNT" = "true" ]; then
    need_link "$ROOT/.claude/skills" "../.agents/skills" ".claude/skills"
  fi

  # Per-adapter wiring, each gated on its adapter= declaration. Length check
  # first: bash 3.2's `set -u` treats an empty array as unbound on
  # expansion (same guard as topology_user_tier_checks).
  local a
  if [ "${#ADAPTERS[@]}" -gt 0 ]; then
    for a in "${ADAPTERS[@]}"; do
      case "$a" in
        claude-code)
          _embedded_check_claude_settings_hooks
          _embedded_check_external_cc_hop
          _sweep_orphan_external_hops
          ;;
        codex)
          _embedded_check_codex_hooks_json
          ;;
        opencode)
          _embedded_check_opencode_instructions
          ;;
        pi)
          _embedded_check_pi_extensions
          ;;
      esac
    done
  fi
}

topology_user_tier_checks() {
  # Extra payload sanity beyond check_payload's memory-index check: the
  # tier's other core artifact, the home-hop source file itself.
  [ -f "$ROOT/AGENTS.md" ] || report_drift "AGENTS.md missing"

  # Canonical home hop: unconditional, not gated on any adapter declaration.
  # shellcheck disable=SC2088  # the "~/..." strings here and in the adapter arms below are display LABELS, never paths - the tilde is meant literally
  need_link "$HOME/AGENTS.md" "$ROOT/AGENTS.md" "~/AGENTS.md"

  # Per-tool global adapters, each gated on its adapter= declaration.
  # bash 3.2's `set -u` treats an empty array as unbound on expansion, so
  # the length check comes first (same guard as check_hook_scripts' loops).
  local a
  if [ "${#ADAPTERS[@]}" -gt 0 ]; then
    for a in "${ADAPTERS[@]}"; do
      case "$a" in
        claude-code)
          # shellcheck disable=SC2088  # display label
          need_link "$HOME/.claude/CLAUDE.md" "$HOME/AGENTS.md" "~/.claude/CLAUDE.md"
          ;;
        codex)
          # shellcheck disable=SC2088  # display label
          need_link "$HOME/.codex/AGENTS.md" "$HOME/AGENTS.md" "~/.codex/AGENTS.md"
          ;;
        opencode)
          # shellcheck disable=SC2088  # display label
          need_link "$HOME/.config/opencode/AGENTS.md" "$HOME/AGENTS.md" "~/.config/opencode/AGENTS.md"
          ;;
      esac
    done
  fi
}

check_role_tier_readiness() {
  # Role-tier readiness (claude-personas#49 spec section 5): active only
  # when the manifest declares role_source (validated in Task 1: never on
  # user-tier, never absolute). Target checks: the path resolves, is a git
  # repo, and its manifest declares memory_layout=roles - a flat target
  # means the pointer was wired before the user-memory migration (spec
  # section 3) and is an ERROR, not a fixable drift.
  [ -n "$ROLE_SOURCE" ] || return 0

  local src_abs target_layout
  src_abs="$(cd "$ROOT/$ROLE_SOURCE" 2>/dev/null && pwd)"
  if [ -z "$src_abs" ]; then
    report_error "role_source '$ROLE_SOURCE' unreachable from $ROOT"
    return 0
  fi
  # -e, not -d: in a worktree or submodule checkout .git is a file.
  if [ ! -e "$src_abs/.git" ]; then
    report_error "role_source '$ROLE_SOURCE' ($src_abs) is not a git repo"
    return 0
  fi
  target_layout="$(grep -v '^[[:space:]]*#' "$src_abs/.agents/manifest" 2>/dev/null \
    | grep '^memory_layout=' | head -n1 | cut -d= -f2-)"
  if [ "$target_layout" != "roles" ]; then
    report_error "role_source '$ROLE_SOURCE' declares memory_layout='${target_layout:-MISSING}', expected 'roles' - wire role_source only after the user-memory migration (claude-personas#49 spec section 3)"
    return 0
  fi

  # Per-role discovery walks root-level dirs, which are roles only under
  # memory_layout=roles; on a flat instance they are code dirs, and fix
  # mode could materialize user symlinks into a stray dir that happens to
  # carry a MEMORY.md (claude-personas#72). Target checks above still ran.
  if [ "$MEMORY_LAYOUT" != "roles" ]; then
    echo "INFO: role_source declared with memory_layout=$MEMORY_LAYOUT - per-role <role>/user checks skipped (root-level dirs are roles only under memory_layout=roles)"
    return 0
  fi

  _role_tier_check_roles "$src_abs"
}

_role_tier_check_roles() {
  # _role_tier_check_roles <src_abs>
  # Per-role <role>/user mount checks (claude-personas#49 spec sections 4d
  # + 5). Role discovery: same rule as check_payload / list-roles.sh - a
  # root-level dir with MEMORY.md, excluding shared and examples.
  # Lazy by design: NO symlink and NO target role dir is the normal state
  # (silent in both modes); fix mode materializes the symlink only once the
  # target role dir exists; --check never flags a missing symlink (creation
  # is fix-mode's job, not a drift). An EXISTING symlink is held to the
  # full standard: exact ../<role_source>/<role> target text AND resolving.
  local src_abs="$1"
  local d n link_path expected_target

  for d in "$ROOT"/*/; do
    [ -d "$d" ] || continue
    n="$(basename "$d")"
    [ -f "$d/MEMORY.md" ] || continue
    if is_reserved_name "$n"; then
      continue
    fi

    link_path="$ROOT/$n/user"
    expected_target="../$ROLE_SOURCE/$n"

    if [ -L "$link_path" ]; then
      need_link "$link_path" "$expected_target" "$n/user"
      if [ -L "$link_path" ] && [ ! -e "$link_path" ] && [ "$(readlink "$link_path")" = "$expected_target" ]; then
        report_drift "$n/user -> $(readlink "$link_path") dangles - role@user dir missing at $src_abs/$n (restore it there or remove the symlink)"
      fi
    elif [ -e "$link_path" ]; then
      report_drift "$n/user exists and is not a symlink (refusing to touch)"
    elif [ -f "$src_abs/$n/MEMORY.md" ] && [ "$CHECK" != 1 ]; then
      need_link "$link_path" "$expected_target" "$n/user"
    fi
  done
}

# Shared floor for every topology, run before the topology-specific catalog.
check_payload
check_hook_scripts
check_framework_staleness

case "$TOPOLOGY" in
  role-clones) topology_role_clones_checks ;;
  embedded) topology_embedded_checks ;;
  user-tier) topology_user_tier_checks ;;
esac

check_role_tier_readiness

if [ "$DRIFT_COUNT" -gt 0 ]; then
  exit 1
fi

echo "OK: $TOPOLOGY instance at $ROOT - all declared wiring verified"
exit 0
