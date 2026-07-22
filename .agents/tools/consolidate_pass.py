#!/usr/bin/env python3
"""consolidate_pass.py - deterministic git wrapper for the consolidation pass (#89).

The only sanctioned write path for the consolidate-memory skill. Owns the git
surface so the AC guarantees are properties of code, not instructions:
zero writes to main (commit refuses off the pass branch), single-store scope
(commit rejects out-of-store paths), typed one-op-per-commit history, and a
DELTA index<->file sync gate at finish - begin snapshots the store's
pre-existing sync findings, finish blocks only on findings the pass
introduced and warns about the rest (#97). Spec:
docs/superpowers/specs/2026-07-16-consolidation-pass-mechanics-design.md

Usage:
    python3 consolidate_pass.py begin --store DIR
    python3 consolidate_pass.py commit --op {dedupe,redistribute,retire} -m MSG
    python3 consolidate_pass.py flag --kind cross-tier-dup -m MSG
    python3 consolidate_pass.py finish
    python3 consolidate_pass.py abort

State lives in local git config (consolidate.store/.base/.branch/.baseref),
following git-flow's config-namespace precedent - nothing eval-visible in the tree.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys

OPS = ("dedupe", "redistribute", "retire")
FLAG_KINDS = ("cross-tier-dup",)
KEYS = ("consolidate.store", "consolidate.base",
        "consolidate.branch", "consolidate.baseref")

# #102 flag-don't-fix: read scope != write scope. The pass may READ adjacent
# tiers for context, but a cross-tier near-duplicate is never fixed - it is
# flagged, and the human routes it. Four distinct situations look identical
# to the pass, and only one of them is a cleanup:
DISPOSITION_MENU = """\
Disposition menu - route each flag by hand:
1. promotion residue -> retire the lower-tier copy (within-store op in a later pass)
2. intentional shadowing (load-bearing delta) -> leave alone
3. promotion signal (same lesson written independently in a second scope) -> \
route to the promotion ladder as evidence; do NOT dedupe
4. post-promotion divergence (both copies edited since) -> human judgment on content"""

INDEX_LINK_RE = re.compile(r"\]\(([^)]+\.md)\)")
# Format examples are not index entries (#97): a link shown in inline code
# (cerebrum's index header documents its own format that way) or a fenced
# block must not register with INDEX_LINK_RE.
_CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
_FENCE_BLOCK_RE = re.compile(r"^(```|~~~).*?^\1", re.DOTALL | re.MULTILINE)


def _git(root: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root, *args],
                          check=check, capture_output=True, text=True)


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def repo_root(cwd: str = ".") -> str | None:
    r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def config_get(root: str, key: str) -> str | None:
    r = _git(root, "config", "--local", "--get", key, check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def config_set(root: str, key: str, value: str) -> None:
    _git(root, "config", "--local", key, value)


def config_unset(root: str, key: str) -> None:
    _git(root, "config", "--local", "--unset", key, check=False)


def _dirty(root: str) -> bool:
    return bool(_git(root, "status", "--porcelain").stdout.strip())


def _current_branch(root: str) -> str:
    return _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def store_relpath(root: str, store: str) -> str | None:
    """Store dir as a relpath under root, or None if outside/invalid.
    A store that IS the repo root (rel == ".") is a legitimate shape -
    it returns "." rather than being rejected. This assumes the root
    contains ONLY the index and fact files (no README.md or other
    root-level .md siblings), matching the canary-eval fixture's shape;
    index_sync_errors requires every root .md except MEMORY.md to be
    indexed, so a root store with an un-indexed doc file can never finish."""
    ab = os.path.realpath(store)
    rootab = os.path.realpath(root)
    if not (ab == rootab or ab.startswith(rootab + os.sep)):
        return None
    return os.path.relpath(ab, rootab)


def changed_paths(root: str) -> list[str]:
    """Working-tree changes vs HEAD. Rename lines (`old -> new`) yield BOTH
    endpoints, so a rename that crosses the store boundary on either side
    is visible to the offender check."""
    out = _git(root, "status", "--porcelain").stdout
    paths = []
    for line in out.splitlines():
        path = line[3:]
        if " -> " in path:
            old, new = path.split(" -> ", 1)
            paths.append(old.strip().strip('"'))
            paths.append(new.strip().strip('"'))
        else:
            paths.append(path.strip().strip('"'))
    return paths


def cmd_commit(args: argparse.Namespace) -> int:
    root = repo_root()
    if root is None:
        return _fail("not inside a git repository")
    branch = config_get(root, "consolidate.branch")
    store = config_get(root, "consolidate.store")
    if not branch or not store:
        return _fail("no consolidation pass in progress; run begin first")
    if _current_branch(root) != branch:
        return _fail(f"not on the pass branch {branch}; refusing to commit")
    paths = changed_paths(root)
    if not paths:
        return _fail("nothing to commit")
    # store == "." means the store IS the repo root, so every changed path
    # is in-store by definition - skip the filter rather than compare
    # against a nonsensical "./" prefix.
    offenders = [] if store == "." else [
        p_ for p_ in paths if not (p_ == store or p_.startswith(store + "/"))]
    if offenders:
        print("FAIL: changes outside the store; revert these and retry:",
              file=sys.stderr)
        for o in offenders:
            print(f"  {o}", file=sys.stderr)
        return 1
    _git(root, "add", "-A", "--", store)
    _git(root, "commit", "-m", f"consolidate({args.op}): {args.m}")
    print(f"OK: consolidate({args.op}): {args.m}")
    return 0


def branch_slug(rel: str) -> str:
    """Git-ref-safe branch component for the store's relative path (#95).
    The live hazard is a dot-directory store: `.agents/memory` (the
    framework's own instance layout) naively becomes a ref component
    starting with `.`, which `git check-ref-format` rejects. Conservative
    rule: keep [A-Za-z0-9_-], map everything else (path separators
    included) to `-`, collapse runs, trim `-` at the ends; if nothing
    survives, fall back to `store` so begin never builds an invalid ref."""
    slug = re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9_-]", "-", rel)).strip("-")
    return slug or "store"


def cmd_begin(args: argparse.Namespace) -> int:
    # Derive root from the store dir itself, not its parent: `git
    # rev-parse --show-toplevel` finds the enclosing repo regardless of
    # depth, so this works whether the store is a subdir OR is itself the
    # repo root (the canary-eval fixture's shape).
    root = repo_root(os.path.realpath(args.store))
    if root is None:
        return _fail(f"{args.store} is not inside a git repository")
    if _dirty(root):
        return _fail("working tree is dirty; commit or stash first")
    rel = store_relpath(root, args.store)
    if rel is None or not os.path.isfile(os.path.join(root, rel, "MEMORY.md")):
        return _fail(f"{args.store} is not a memory store (no MEMORY.md)")
    if config_get(root, "consolidate.branch"):
        return _fail("a consolidation pass is already in progress; run finish or abort")
    slug = "root" if rel == "." else branch_slug(rel)
    branch = f"consolidate/{slug}-{datetime.date.today().isoformat()}"
    if _git(root, "rev-parse", "--verify", branch, check=False).returncode == 0:
        return _fail(f"branch {branch} already exists; delete it or finish that pass")
    baseref = _current_branch(root)
    if baseref == "HEAD":
        return _fail("detached HEAD; check out a branch before starting a pass")
    base = _git(root, "rev-parse", "HEAD").stdout.strip()
    _git(root, "checkout", "-q", "-b", branch)
    config_set(root, "consolidate.store", rel)
    config_set(root, "consolidate.base", base)
    config_set(root, "consolidate.branch", branch)
    config_set(root, "consolidate.baseref", baseref)
    # Snapshot the store's sync errors as they stand BEFORE the pass: finish
    # holds the pass accountable only for its own delta (#97), so pre-existing
    # rot (layered-index conventions, historical drift) never blocks delivery.
    preexisting = index_sync_errors(root, rel)
    with open(snapshot_path(root), "w", encoding="utf-8") as f:
        f.write("\n".join(preexisting))
    if preexisting:
        print(f"NOTE: {len(preexisting)} pre-existing index-sync finding(s) "
              "recorded; finish will warn about them but only block on NEW ones")
    print(f"OK: pass branch {branch} (store: {rel}, base: {baseref})")
    return 0


def index_sync_errors(root: str, store: str) -> list[str]:
    """Index<->file sync, same-directory links only - cross-store references
    like shared/MEMORY.md are legitimate and skipped, as are URLs. A leading
    `./` on a same-directory link (e.g. `./fact_a.md`) is normalized away
    before the cross-store filter, so it isn't mistaken for a path. Inline
    code spans and fenced blocks are stripped first - a format example in
    the index header is not a link (#97)."""
    storedir = os.path.join(root, store)
    idx_path = os.path.join(storedir, "MEMORY.md")
    with open(idx_path, encoding="utf-8") as f:
        text = _CODE_SPAN_RE.sub("", _FENCE_BLOCK_RE.sub("", f.read()))
    links = INDEX_LINK_RE.findall(text)
    links = [l[2:] if l.startswith("./") else l for l in links]
    linked = {l for l in links if "/" not in l and "://" not in l}
    on_disk = {f_ for f_ in os.listdir(storedir)
               if f_.endswith(".md") and f_ != "MEMORY.md"}
    errors = []
    for ghost in sorted(linked - on_disk):
        errors.append(f"index links missing file: {ghost}")
    for orphan in sorted(on_disk - linked):
        errors.append(f"file not in index: {orphan}")
    return errors


def snapshot_path(root: str) -> str:
    """Where begin records the store's PRE-EXISTING sync errors (#97): inside
    the git dir, so it is invisible to the working tree and to the eval, and
    dies with the pass state rather than lingering as a tracked file."""
    d = _git(root, "rev-parse", "--git-dir").stdout.strip()
    if not os.path.isabs(d):
        d = os.path.join(root, d)
    return os.path.join(d, "consolidate-preexisting")


def _remove_snapshot(root: str) -> None:
    try:
        os.remove(snapshot_path(root))
    except OSError:
        pass


def flags_path(root: str) -> str:
    """Where flag entries accumulate during a pass (#102): inside the git
    dir, same rationale as snapshot_path - flags are report-only state, so
    they must never appear in the working tree or become commits."""
    d = _git(root, "rev-parse", "--git-dir").stdout.strip()
    if not os.path.isabs(d):
        d = os.path.join(root, d)
    return os.path.join(d, "consolidate-flags")


def read_flags(root: str) -> list[str]:
    try:
        with open(flags_path(root), encoding="utf-8") as f:
            return [line for line in f.read().splitlines() if line.strip()]
    except OSError:
        return []


def _remove_flags(root: str) -> None:
    try:
        os.remove(flags_path(root))
    except OSError:
        pass


def flags_report(flags: list[str]) -> str:
    """Human-facing flags block, shared by the PR body and the stdout
    report paths: the entries plus the four-way disposition menu."""
    lines = ["Flags (report-only - no commits were made for these):", ""]
    lines += [f"- {f}" for f in flags]
    lines += ["", DISPOSITION_MENU]
    return "\n".join(lines)


def pr_body(ops: list[str], flags: list[str]) -> str:
    body = "Consolidation pass operations:\n\n" + "\n".join(f"- {s}" for s in ops)
    if flags:
        body += "\n\n" + flags_report(flags)
    return body


def cmd_flag(args: argparse.Namespace) -> int:
    root = repo_root()
    if root is None:
        return _fail("not inside a git repository")
    branch = config_get(root, "consolidate.branch")
    if not branch:
        return _fail("no consolidation pass in progress; run begin first")
    if _current_branch(root) != branch:
        return _fail(f"not on the pass branch {branch}; refusing to flag")
    # One flag = one line: collapse any whitespace runs (newlines included)
    # so a multi-line -m can't split into prefix-less phantom entries.
    entry = f"flag({args.kind}): {' '.join(args.m.split())}"
    with open(flags_path(root), "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    print(f"OK: {entry} (report-only; delivered by finish, never committed)")
    return 0


def _op_log(root: str, base: str) -> list[str]:
    out = _git(root, "log", "--reverse", "--format=%s", f"{base}..HEAD").stdout
    return [s for s in out.splitlines() if s.strip()]


def _clear_state(root: str) -> None:
    """Terminal-path finalization: drop the config keys + the #97 snapshot.
    Shared by every path that ends a pass (finish successes, zero-op
    cleanup, abort) so no ending can forget half the state."""
    for key in KEYS:
        config_unset(root, key)
    _remove_snapshot(root)
    _remove_flags(root)


def _cleanup(root: str, branch: str, baseref: str) -> None:
    _git(root, "checkout", "-q", baseref)
    _git(root, "branch", "-D", branch)
    _clear_state(root)


def cmd_finish(args: argparse.Namespace) -> int:
    root = repo_root()
    if root is None:
        return _fail("not inside a git repository")
    branch = config_get(root, "consolidate.branch")
    store = config_get(root, "consolidate.store")
    base = config_get(root, "consolidate.base")
    baseref = config_get(root, "consolidate.baseref")
    if not all((branch, store, base, baseref)):
        return _fail("no consolidation pass in progress; run begin first")
    if _current_branch(root) != branch:
        return _fail(f"not on the pass branch {branch}")
    if _dirty(root):
        return _fail("uncommitted changes; land them via commit or revert them")
    ops = _op_log(root, base)
    flags = read_flags(root)
    if not ops:
        # A flags-only pass has no commits, hence no branch/PR to deliver:
        # stdout IS its report channel. Print before cleanup clears them.
        if flags:
            print("OK: nothing to consolidate; "
                  f"{len(flags)} flag(s) for human routing:\n")
            print(flags_report(flags))
        else:
            print("OK: nothing to consolidate; cleaning up")
        _cleanup(root, branch, baseref)
        return 0
    idx_path = os.path.join(root, store, "MEMORY.md")
    if not os.path.isfile(idx_path):
        return _fail(f"{store}/MEMORY.md missing - the pass must never delete the store index")
    errors = index_sync_errors(root, store)
    try:
        with open(snapshot_path(root), encoding="utf-8") as f:
            preexisting = {line for line in f.read().splitlines() if line}
    except OSError:
        preexisting = set()   # no snapshot (pre-#97 begin): all errors block
    new_errors = [e for e in errors if e not in preexisting]
    if new_errors:
        for e in new_errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return _fail(f"{len(new_errors)} index-sync error(s) INTRODUCED by this "
                     "pass; fix them via commit, then retry finish")
    still_present = [e for e in errors if e in preexisting]
    if still_present:
        print(f"WARN: {len(still_present)} pre-existing index-sync finding(s) "
              "remain (not introduced by this pass; not a delivery blocker):",
              file=sys.stderr)
        for e in still_present:
            print(f"  {e}", file=sys.stderr)
    if not _git(root, "remote", check=False).stdout.strip():
        _clear_state(root)
        print(f"OK: {len(ops)} operation(s) on {branch} (no remote; branch is the deliverable)")
        if flags:
            print()
            print(flags_report(flags))
        return 0
    # Same slug rule as begin: "root" for a store-at-repo-root pass, else
    # the store's relpath - keeps the PR title consistent with the branch
    # name instead of printing the raw "." store string.
    slug = "root" if store == "." else store
    title = f"consolidate: {slug} pass {datetime.date.today().isoformat()}"
    body = pr_body(ops, flags)
    if not shutil.which("gh"):
        return _fail("gh not found; branch intact - deliver manually:\n"
                     f"  git push -u origin {branch}\n"
                     f"  gh pr create --title '{title}' --body-file <ops>")
    push = _git(root, "push", "-u", "origin", branch, check=False)
    if push.returncode != 0:
        print(push.stderr, file=sys.stderr)
        return _fail("push failed; branch intact - deliver manually:\n"
                     f"  git push -u origin {branch}\n"
                     f"  gh pr create --title '{title}' --body-file <ops>")
    pr = subprocess.run(["gh", "pr", "create", "--title", title, "--body", body],
                        cwd=root, capture_output=True, text=True)
    if pr.returncode != 0:
        print(pr.stderr, file=sys.stderr)
        return _fail("gh pr create failed; branch pushed - open the PR manually:\n"
                     f"  gh pr create --title '{title}' --body '...op log...'")
    _clear_state(root)
    print(f"OK: PR opened for {branch}\n{pr.stdout.strip()}")
    return 0


def cmd_abort(args: argparse.Namespace) -> int:
    root = repo_root()
    if root is None:
        return _fail("not inside a git repository")
    branch = config_get(root, "consolidate.branch")
    baseref = config_get(root, "consolidate.baseref")
    if not branch or not baseref:
        return _fail("no consolidation pass in progress")
    _git(root, "checkout", "-qf", baseref)
    _git(root, "branch", "-D", branch)
    _clear_state(root)
    print(f"OK: aborted; back on {baseref}, {branch} deleted")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("begin")
    b.add_argument("--store", required=True)
    b.set_defaults(fn=cmd_begin)
    c = sub.add_parser("commit")
    c.add_argument("--op", required=True, choices=OPS)
    c.add_argument("-m", required=True)
    c.set_defaults(fn=cmd_commit)
    fl = sub.add_parser("flag")
    fl.add_argument("--kind", required=True, choices=FLAG_KINDS)
    fl.add_argument("-m", required=True)
    fl.set_defaults(fn=cmd_flag)
    f = sub.add_parser("finish")
    f.set_defaults(fn=cmd_finish)
    a = sub.add_parser("abort")
    a.set_defaults(fn=cmd_abort)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
