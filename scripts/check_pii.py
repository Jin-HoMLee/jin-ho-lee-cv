"""PII-leak guard: block private values (phone, street, postal code) and PII paths.

One detection core, three enforcement surfaces:

  --staged   check staged files (git pre-commit hook); exit 1 on violation
  --tree     check all tracked files (CI backstop); exit 1 on violation
  --hook     read PreToolUse JSON on stdin; deny `git commit` when staged files
             leak PII, otherwise allow silently (Claude Code Bash hook)

`scan_files` is a pure function (path string + content bytes in, violations out)
so the detection logic is testable without git. Guarded keys: `phone`,
`address.street`, `address.postal_code`. `address.city` and `country` are
intentionally public (the CV header already shows "Mannheim, GER") and excluded.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


yaml = YAML(typ="safe")

REPO_ROOT = Path(__file__).parent.parent
PRIVATE_YAML = REPO_ROOT / "content.private" / "private.yaml"

# Staged/tracked files under these roots must never be committed. Dir roots end
# in "/" (prefix match); the rest are fnmatch globs.
PII_PATH_ROOTS = (
    "content.private/",
    "applications/",
    "assets/photo.*",
    "assets/signature.*",
)
# Explicitly tracked placeholders — never PII even though the prefix is similar.
PII_PATH_ALLOW = ("content.private.example/",)


class PrivateConfigError(Exception):
    """content.private/private.yaml exists but can't be parsed (fail-closed)."""


@dataclass(frozen=True)
class Violation:
    path: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


def load_private_values(private_path: Path = PRIVATE_YAML) -> set[str]:
    """Return the set of guarded private literals; empty set if the file is absent.

    Guards phone + address.street + address.postal_code. Excludes the
    intentionally-public address.city and country.
    """
    if not private_path.exists():
        return set()
    try:
        with private_path.open("r", encoding="utf-8") as f:
            data = yaml.load(f) or {}
    except YAMLError as e:
        # Report only the location, never the offending line's content (it's PII).
        mark = getattr(e, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark is not None else ""
        raise PrivateConfigError(
            f"content.private/private.yaml is malformed{where} — the PII known-value "
            "scan cannot run. Fix the YAML (quote values containing ':' or special "
            "characters) or move the file aside."
        ) from None

    values: set[str] = set()
    phone = data.get("phone")
    if phone:
        values.add(str(phone).strip())
    address = data.get("address") or {}
    for key in ("street", "postal_code"):
        value = address.get(key)
        if value:
            values.add(str(value).strip())
    return {v for v in values if v}


def _is_pii_path(path: str, roots=PII_PATH_ROOTS, allow=PII_PATH_ALLOW) -> bool:
    norm = path.replace("\\", "/")
    if any(norm.startswith(a) for a in allow):
        return False
    for root in roots:
        if root.endswith("/"):
            if norm.startswith(root):
                return True
        elif fnmatch.fnmatch(norm, root):
            return True
    return False


def scan_files(
    files, private_values, roots=PII_PATH_ROOTS, allow=PII_PATH_ALLOW
) -> list[Violation]:
    """Pure detection core.

    `files` is an iterable of (path: str, content: bytes | None). `content` is
    None for files that couldn't be read (binary still hits the path guard).
    Returns one Violation per offending file.
    """
    violations: list[Violation] = []
    for path, content in files:
        if _is_pii_path(path, roots, allow):
            violations.append(Violation(path, "tracked file under a gitignored PII path"))
            continue
        if content is None:
            continue
        try:
            text = content.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            continue  # binary / undecodable — path guard already had its turn
        if any(value in text for value in private_values):
            # Never echo the matched value — that would re-leak it into logs.
            violations.append(Violation(path, "contains a guarded private value"))
    return violations


# ---- git wrappers (thin, impure) ------------------------------------------


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        shell=False,
    )
    return proc.stdout


def _staged_paths() -> list[str]:
    out = _git("diff", "--cached", "--name-only", "--diff-filter=ACM")
    return [line for line in out.splitlines() if line]


def _tracked_paths() -> list[str]:
    out = _git("ls-files")
    return [line for line in out.splitlines() if line]


def _read_staged_blob(path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "show", f":{path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        shell=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def _read_worktree(path: str) -> bytes | None:
    try:
        return (REPO_ROOT / path).read_bytes()
    except OSError:
        return None


def _staged_files():
    return [(p, _read_staged_blob(p)) for p in _staged_paths()]


def _tracked_files():
    return [(p, _read_worktree(p)) for p in _tracked_paths()]


def run_staged_scan() -> list[Violation]:
    return scan_files(_staged_files(), load_private_values())


# ---- hook mode ------------------------------------------------------------


def _is_git_commit(command: str) -> bool:
    """True if any `&&`/`;`/`|`-separated segment is a `git commit` invocation."""
    for segment in command.replace("&&", "\n").replace("||", "\n").replace(";", "\n").split("\n"):
        for piece in segment.split("|"):
            tokens = piece.split()
            if not tokens or tokens[0] != "git":
                continue
            i = 1
            while i < len(tokens):
                tok = tokens[i]
                if tok in ("-c", "-C"):  # global option that takes a value
                    i += 2
                    continue
                if tok.startswith("-"):
                    i += 1
                    continue
                if tok == "commit":  # first subcommand token
                    return True
                break  # some other subcommand
    return False


def hook_decision(stdin_text: str, scan_fn=run_staged_scan) -> dict | None:
    """Map PreToolUse stdin to a deny payload, or None to allow silently.

    `scan_fn` is injectable for testing; defaults to the real staged scan.
    """
    try:
        payload = json.loads(stdin_text)
        command = payload["tool_input"]["command"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(command, str) or not _is_git_commit(command):
        return None
    try:
        violations = scan_fn()
    except PrivateConfigError as e:
        # Fail-closed: a guard that can't run must not wave the commit through.
        return _deny(f"PII guard could not run — {e} Commit blocked (fail-closed).")
    if not violations:
        return None
    paths = ", ".join(sorted({v.path for v in violations}))
    return _deny(
        "PII guard blocked this commit — staged files would leak private "
        f"content.private values or paths: {paths}. Unstage them before committing."
    )


def _deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


# ---- CLI ------------------------------------------------------------------


def _report(violations: list[Violation]) -> int:
    if violations:
        print(f"FAIL: {len(violations)} PII violation(s)", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("OK: no PII leaks detected")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="check staged files (pre-commit)")
    mode.add_argument("--tree", action="store_true", help="check all tracked files (CI)")
    mode.add_argument("--hook", action="store_true", help="PreToolUse stdin → deny git commit")
    args = parser.parse_args(argv)

    if args.hook:
        decision = hook_decision(sys.stdin.read())
        if decision is not None:
            print(json.dumps(decision))
        return 0  # decision is conveyed via JSON, not exit code

    # --staged: pre-commit. --tree: CI backstop (no content.private/ → path-guard only).
    scan = (
        run_staged_scan
        if args.staged
        else lambda: scan_files(_tracked_files(), load_private_values())
    )
    try:
        violations = scan()
    except PrivateConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1  # fail-closed: block rather than skip the known-value scan
    return _report(violations)


if __name__ == "__main__":
    raise SystemExit(main())
