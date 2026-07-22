#!/usr/bin/env bash
# inject-subagent-role-pointer.sh - Claude Code SubagentStart hook for a
# personas instance: inject a ~250-byte POINTER naming the spawning role
# subagent's memory indexes, never the payload (claude-personas#64 pilot:
# CC silently clips hook additionalContext at ~2 KB on this path, so the
# subagent must Read the files itself - its definition must grant Read).
#
# Usage: inject-subagent-role-pointer.sh <memory-repo-root>
# stdin: the CC hook JSON; .agent_type selects the role dir. An agent_type
# with no <memory-repo-root>/<agent_type>/MEMORY.md gets nothing - built-in
# and non-role agent types pass through silently.
#
# Wiring note: instance delivery (settings entries) rides the #58
# mechanism; this script is the vendor-neutral payload half.
#
# Defensive by design: never fails a spawn - always exits 0.

set -u

memrepo="${1:-}"
[ -n "$memrepo" ] && [ -d "$memrepo" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

agent_type="$(jq -r '.agent_type // empty' 2>/dev/null)"
[ -n "$agent_type" ] || exit 0
# Role dir names are plain slugs; anything else (path separators, dots)
# is not a role and must not become a path component. shared/examples are
# the same non-role exclusion every other role-discovery component applies,
# folded to lowercase: on a case-insensitive filesystem (macOS APFS
# default) Shared/MEMORY.md resolves to shared/MEMORY.md.
case "$agent_type" in
  *[!a-zA-Z0-9_-]*) exit 0 ;;
esac
case "$(printf '%s' "$agent_type" | tr '[:upper:]' '[:lower:]')" in
  shared|examples) exit 0 ;;
esac

role_index="$memrepo/$agent_type/MEMORY.md"
[ -r "$role_index" ] || exit 0

ptr="You are the $agent_type role. Before acting: Read $role_index"
if [ -r "$memrepo/$agent_type/shared/MEMORY.md" ]; then
  ptr="$ptr ; then Read $memrepo/$agent_type/shared/MEMORY.md"
fi
if [ -r "$memrepo/$agent_type/user/MEMORY.md" ]; then
  ptr="$ptr ; then Read $memrepo/$agent_type/user/MEMORY.md"
fi
ptr="$ptr . These are routing indexes - follow links relevant to your task; do not read another role's directory."

jq -nc --arg ctx "$ptr" \
  '{hookSpecificOutput:{hookEventName:"SubagentStart",additionalContext:$ctx}}' 2>/dev/null || true
exit 0
