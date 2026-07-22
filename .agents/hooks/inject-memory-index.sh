#!/usr/bin/env bash
# inject-memory-index.sh - Codex SessionStart hook for this embedded instance:
# inject the repo's memory index (.agents/memory/MEMORY.md) as
# additionalContext, mirroring Claude Code's native auto-memory load.
#
# Instance-owned wrapper: the generated .codex/hooks.json calls hooks with no
# arguments, and the framework's inject-role-index.sh needs the memory dir as
# $1 - this wrapper supplies it. The memory dir is gitignored (this repo is
# public), so on a clone without memory the lib script no-ops gracefully.
set -u
here="$(cd "$(dirname "$0")" && pwd -P)"
exec "$here/lib/inject-role-index.sh" "$here/../memory"
