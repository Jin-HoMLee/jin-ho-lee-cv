#!/usr/bin/env bash
# inject-role-index.sh - Codex SessionStart hook payload for a role clone:
# inject the role's always-loaded memory INDEX (its MEMORY.md) as
# additionalContext, mirroring Claude Code's native auto-load of the role file.
# Ships in the memory repo; the per-clone generated .codex/hooks.json (see
# init-clone.sh) calls it with the absolute role dir.
#
# Usage: inject-role-index.sh <absolute-role-dir>
#
# SCOPE - role index only, NOT shared (claude-personas#52). Claude Code
# auto-injects the role MEMORY.md but not shared/MEMORY.md; shared reaches
# context lazily via the load-persona-memory skill and file-relative links.
# This script mirrors that for cross-vendor parity: it injects only the role
# index and appends a one-line pointer to the on-demand shared index.
#
# CAP - adopts Claude Code's native MEMORY.md size guard rather than an invented
# figure (CC v2.1.186 truncates the auto-injected role index at ~200 lines /
# ~25 KB, whichever first; source: the splice MM reference
# reference_native_memory_compaction.md, cross-checked in claude-personas#48).
# The payload is bounded to whole lines only, with an explicit [TRUNCATED ...]
# trailer when it cuts, so the cut is curated instead of the vendor slicing
# arbitrarily through the middle. Both thresholds are overridable via
# PERSONAS_INJECT_BYTE_CAP / PERSONAS_INJECT_LINE_CAP (a single canonical source
# for the CC figure is the #48 fast-follow).
#
# Defensive by design: never fails the session start - always exits 0.

set -u

role_dir="${1:-}"
[ -n "$role_dir" ] && [ -d "$role_dir" ] || exit 0
command -v jq >/dev/null 2>&1 || {
  echo "inject-role-index: jq not found - index NOT injected; read $role_dir/MEMORY.md manually" >&2
  exit 0
}

# Claude Code native role-index truncation thresholds (whichever hits first).
# Fall back to the defaults on an empty or non-numeric override rather than
# letting awk coerce garbage to 0 and silently suppress the whole index.
byte_cap="${PERSONAS_INJECT_BYTE_CAP:-25000}"
line_cap="${PERSONAS_INJECT_LINE_CAP:-200}"
case "$byte_cap" in ''|*[!0-9]*) byte_cap=25000;; esac
case "$line_cap" in ''|*[!0-9]*) line_cap=200;; esac

role_index="$role_dir/MEMORY.md"
[ -r "$role_index" ] || exit 0

hdr="# Role memory index
"
# Byte budget left for role-index lines after the header.
remaining=$(( byte_cap - ${#hdr} ))
[ "$remaining" -le 0 ] && exit 0

# Keep whole lines while BOTH the byte budget and the line cap still hold. awk
# signals a REAL cut via exit 3, so the truncation flag never depends on
# line-count arithmetic - which a blank-line EOF (command substitution strips
# trailing blank lines from the chunk) or a missing final newline would
# otherwise mislead into a false (or missed) truncation notice.
chunk="$(awk -v bcap="$remaining" -v lcap="$line_cap" '
  { n += length($0) + 1; if (n > bcap || NR > lcap) { cut = 1; exit } print }
  END { if (cut) exit 3 }
' "$role_index")"
awk_rc=$?

payload="$hdr$chunk
"
truncated=0
[ "$awk_rc" -eq 3 ] && truncated=1

# Shared index is loaded on demand (parity with CC, which does not auto-inject
# shared). Point at it when it exists - the model reaches it via the
# load-persona-memory skill or file-relative links, not this payload.
if [ -r "$role_dir/shared/MEMORY.md" ]; then
  payload="$payload
# Shared memory index (loaded on demand): read $role_dir/shared/MEMORY.md"
fi

# role@user index (claude-personas#49): pointer only, and only when the lazy
# mount exists - reading order mirrors the precedence chain (role > shared >
# role@user), so this line comes after the shared pointer.
if [ -r "$role_dir/user/MEMORY.md" ]; then
  payload="$payload
# Role user-tier memory index (loaded on demand): read $role_dir/user/MEMORY.md"
fi

if [ "$truncated" -eq 1 ]; then
  payload="$payload
[TRUNCATED by the Codex adapter at the Claude Code native cap - read $role_index for the full role index]"
fi

jq -nc --arg ctx "$payload" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}' 2>/dev/null || true
exit 0
