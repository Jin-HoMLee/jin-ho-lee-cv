#!/usr/bin/env bash
# list-roles.sh — audit v3 role clones in this memory repo's parent dir.
#
# Walks $PARENT/<project>* sibling directories, reports for each:
#   role (from .claude/memory/ symlink target), symlink status, git status.
#
# Run from inside your memory repo (claude-personas-<app>/).

set -uo pipefail

MEMORY_REPO="$( pwd )"
PARENT_DIR="$( dirname "$MEMORY_REPO" )"
MEMORY_REPO_NAME="$( basename "$MEMORY_REPO" )"

# Derive project name from memory repo name (strip leading claude-personas-)
PROJECT_NAME="${MEMORY_REPO_NAME#claude-personas-}"

if [[ "$PROJECT_NAME" == "$MEMORY_REPO_NAME" ]]; then
  echo "Error: memory repo name '$MEMORY_REPO_NAME' doesn't start with 'claude-personas-'." >&2
  echo "Cannot derive project name." >&2
  exit 1
fi

# Discover available roles in memory repo
ROLES=()
for d in "$MEMORY_REPO"/*/; do
  n="$(basename "$d")"
  # Reserved non-role names, case-folded (APFS treats Examples/ as
  # examples/). Keep in sync with doctor.sh is_reserved_name -
  # tests/test_framework_files.sh greps every copy and fails on desync.
  case "$(printf '%s' "$n" | tr '[:upper:]' '[:lower:]')" in
    shared|examples) continue ;;
  esac
  if [[ -f "$d/MEMORY.md" ]]; then
    ROLES+=("$n")
  fi
done

printf "%-12s  %-40s  %-25s  %s\n" "Role" "Clone path" "Memory symlink" "Git status"
printf "%-12s  %-40s  %-25s  %s\n" "----" "----------" "---------------" "----------"

healthy=0
broken=0
missing=0

for role in "${ROLES[@]}"; do
  # Candidate paths: the memory repo itself (Memory Manager self-mount,
  # .agents/memory -> ../<role>), then the no-suffix and suffix clones.
  candidates=("$MEMORY_REPO" "$PARENT_DIR/$PROJECT_NAME" "$PARENT_DIR/$PROJECT_NAME-$role")
  found_clone=""
  for cand in "${candidates[@]}"; do
    if [[ ! -d "$cand/.git" ]]; then continue; fi
    # Prefer the vendor-neutral mount (two-hop layout); fall back to the
    # v3.1 direct .claude/memory symlink.
    link=""
    if [[ -L "$cand/.agents/memory" ]]; then
      link="$cand/.agents/memory"
    elif [[ -L "$cand/.claude/memory" ]]; then
      link="$cand/.claude/memory"
    else
      continue
    fi
    target="$(readlink "$link")"
    # Match if symlink target ends with /<role> (handles both healthy and broken symlinks)
    if [[ "$target" == *"/$role" || "$target" == "$role" ]]; then
      found_clone="$cand"
      break
    fi
    # Also claim the role-suffix clone even if symlink points elsewhere (broken re-wire)
    if [[ "$cand" == *"-$role" ]]; then
      found_clone="$cand"
      break
    fi
  done

  if [[ -z "$found_clone" ]]; then
    printf "%-12s  %-40s  %-25s  %s\n" "$role" "<missing>" "—" "—"
    missing=$((missing + 1))
    continue
  fi

  # Inspect symlink health
  resolved="$found_clone/.claude/memory/MEMORY.md"
  if [[ -f "$resolved" ]]; then
    sym_status="OK → $role/"
    healthy=$((healthy + 1))
  else
    sym_status="BROKEN"
    broken=$((broken + 1))
  fi

  # git status
  if ! ( cd "$found_clone" && git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null ); then
    git_status="dirty"
  else
    git_status="clean"
  fi

  # Relative path to clone
  rel="${found_clone#"$PARENT_DIR"/}"
  printf "%-12s  %-40s  %-25s  %s\n" "$role" "$rel/" "$sym_status" "$git_status"
done

echo ""
echo "Summary: $healthy healthy, $broken broken, $missing missing"
[[ "$broken" -eq 0 ]] || exit 1
