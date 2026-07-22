#!/usr/bin/env python3
"""memory_cliff.py - lint each role's always-loaded memory against the tier-1
size budgets (CONVENTIONS.md): rules / lines / ~tokens. Reports each role's
effective per-session load (role + shared) and exits non-zero when any role
exceeds a budget.

Realizes issue #18 (the planned ``scripts/check-budget.sh``). Adapted from the
working counter dogfooded in the ``claude-personas-splice-neoepitope-pipeline``
instance (hand-off: issue #23). Read-only, stdlib-only, zero network.

Usage (framework repo path shown; in an installed instance the tool lives at
.agents/tools/memory_cliff.py):
    python3 framework/tools/memory_cliff.py                 # report + exit 1 if over budget
    python3 framework/tools/memory_cliff.py --root PATH     # lint a different repo root
    python3 framework/tools/memory_cliff.py --write-baseline b.json   # snapshot current load
    python3 framework/tools/memory_cliff.py --baseline b.json         # ratchet: fail on regression
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass

# Tier-1 size budgets, per CONVENTIONS.md ("Size budgets for tier 1"). A role is
# flagged OVER only when it strictly EXCEEDS a budget (`>` in classify): a load
# sitting exactly at the threshold is still OK - the documented cliff value is the
# last good value, not the first bad one (see test_at_threshold_is_ok).
RULE_CLIFF = 14
LINE_CLIFF = 200
TOKEN_CLIFF = 4000

# An always-loaded H2 section is any H2 whose title contains "Always" as a whole
# word immediately followed by whitespace or end-of-line. This matches the template's
# "## Tier 1 - Always in effect" and instance-style sibling loaders like "## Always
# run at session start", while NOT matching:
#   - "## Alwaysish ..."                  (no word boundary after "Always")
#   - "## Notes on Always-in-effect ..."  (hyphen, not whitespace - a prose mention,
#     not a section header; same for "## Overview of Always-loaded memory")
# The lazy "## Tier 2 - Reference" / "## Reference" sections (and role index sections
# like "## Role: PM") never contain "Always".
_ALWAYS_RE = re.compile(r"\bAlways(?=\s|$)")


# --------------------------------------------------------------------------- #
# Leaf pure functions
# --------------------------------------------------------------------------- #
def approx_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars/token (integer floor). stdlib-only - no
    tiktoken (it downloads a BPE vocab on first use). Adequate as a cliff gauge."""
    return len(text) // 4


def _is_always_header(line: str) -> bool:
    """True iff ``line`` is an always-loaded section header: an H2 (``## ``, at
    column 0) whose title contains the word ``Always``. So ``## Tier 1 - Always in
    effect`` (template) and ``## Always run at session start`` (instance) both match,
    while ``## Alwaysish notes`` (no word boundary), ``## Reference``, and an indented
    ``  ## Always ...`` do not."""
    if not line.startswith("## "):
        return False
    return _ALWAYS_RE.search(line) is not None


def extract_section(text: str) -> list[str]:
    """Return the concatenated lines of EVERY always-loaded section in ``text`` -
    each header matching ``_is_always_header`` down to the next ``## `` H2 (or EOF).
    ``### `` subheadings do not terminate a section. Empty list if no always-loaded
    section is present. ``splitlines()`` normalises CRLF so ``\\r``-free lines parse
    identically."""
    lines = text.splitlines()
    section: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        if _is_always_header(lines[i]):
            section.append(lines[i])
            i += 1
            while i < n and not lines[i].startswith("## "):
                section.append(lines[i])
                i += 1
        else:
            i += 1
    return section


def strip_html_comments(text: str) -> str:
    """Remove ``<!-- ... -->`` comment spans (DOTALL, non-greedy) so example rule
    bullets the template ships *inside* comments don't count as live rules, while a
    real rule carrying an inline drift annotation (``- **R:** ... <!-- src: x -->``)
    keeps its ``- **`` line start and still counts. HTML comments don't nest, so the
    first ``-->`` closes - matching how a Markdown renderer reads the file."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def strip_code_fences(lines: list[str]) -> list[str]:
    """Drop lines inside ``` ``` ``` / ``~~~`` fenced code blocks so a rule-format
    example shown in a fence (CONVENTIONS.md does exactly this; a user's MEMORY.md
    may too) doesn't count as a live rule. The opening fence's marker must reappear to
    close, so a ``` ``` ``` block isn't closed by ``~~~``. An unterminated fence (its
    closer fell past the section's ``## `` boundary) swallows the rest of the section -
    conservative, never an over-count. Fence lines still count toward line/token cost."""
    out: list[str] = []
    fence: str | None = None   # active fence marker ("```" or "~~~"), or None
    for line in lines:
        stripped = line.lstrip()
        if fence is None:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fence = stripped[:3]
            else:
                out.append(line)
        elif stripped.startswith(fence):
            fence = None       # close; drop the closing fence line too
    return out


def count_rules(section_lines: list[str]) -> int:
    """Count top-level rule bullets - lines starting ``- **`` (dash, space, two
    asterisks), matching the drift-annotation rule format in CONVENTIONS.md
    (``- **My rule:** ... <!-- src: ... -->``). Commented-out bullets (strip_html_comments)
    and fenced-code-block bullets (strip_code_fences) are dropped first; indented
    sub-bullets (space- or tab-led) and plain ``- `` index bullets (e.g.
    ``- [Shared index](...)``) are excluded."""
    live = strip_code_fences(strip_html_comments("\n".join(section_lines)).splitlines())
    return sum(1 for line in live if line.startswith("- **"))


# --------------------------------------------------------------------------- #
# Per-file metrics
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FileMetrics:
    rules: int
    always_lines: int      # lines across all always-loaded sections (headers included)
    file_lines: int        # whole-file newline count (== `wc -l`)
    tokens: int            # approx tokens of the always-loaded sections
    file_tokens: int = 0   # approx tokens of the WHOLE file (report-only axis)


def analyze_text(text: str, whole_file_is_always: bool = False) -> FileMetrics:
    """``whole_file_is_always=True`` treats the ENTIRE file as the always-loaded
    section instead of extracting a ``## ... Always ...`` subsection - this is the
    flat-layout seam (a flat instance's single index IS the whole tier-1 load;
    flat-topology adapters inject it in full, so there is no section to subtract).
    Reusing this one function for both layouts keeps the rule/line/token counting
    logic in exactly one place; the default (``False``) is byte-for-byte the
    original roles-layout behavior."""
    section = text.splitlines() if whole_file_is_always else extract_section(text)
    return FileMetrics(
        rules=count_rules(section),
        always_lines=len(section),
        file_lines=text.count("\n"),   # newline count == `wc -l`
        tokens=approx_tokens("\n".join(section)),
        file_tokens=approx_tokens(text),
    )


def analyze_file(path: str, whole_file_is_always: bool = False) -> FileMetrics | None:
    """Analyze a MEMORY.md file; return None if it does not exist. Reads as
    ``utf-8-sig`` so a leading BOM is stripped - a BOM would otherwise hide the
    header and silently zero the section. Read/decode errors propagate to the
    caller (``main`` turns them into a clean exit 2). ``whole_file_is_always`` is
    forwarded to ``analyze_text`` - see there."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8-sig") as f:
        return analyze_text(f.read(), whole_file_is_always=whole_file_is_always)


# --------------------------------------------------------------------------- #
# Corpus discovery (topology-driven, no hardcoded role names)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Corpus:
    shared_dir: str | None      # "shared", or None if shared/MEMORY.md absent
    role_dirs: tuple[str, ...]  # sorted role dir names


def _is_role_dir(root: str, name: str) -> bool:
    """A role dir holds BOTH a MEMORY.md file AND a `shared` symlink. The two-part
    test excludes the shared dir itself (MEMORY.md but no symlink) and non-memory
    dirs like docs/ scripts/ (neither marker). ``islink`` is True even for a dangling
    `shared` target - fine here, it's only a role-dir marker; the shared MEMORY.md is
    read via ``corpus.shared_dir``, never through this per-role symlink."""
    d = os.path.join(root, name)
    return os.path.isfile(os.path.join(d, "MEMORY.md")) and os.path.islink(
        os.path.join(d, "shared")
    )


def discover(root: str) -> Corpus:
    """Infer the corpus from ``root``'s top-level layout (so the lint runs on any
    instance - 3 roles or 5 - with zero config). Raises OSError if root is
    unreadable (caller maps to a clean exit 2)."""
    shared_dir = "shared" if os.path.isfile(os.path.join(root, "shared", "MEMORY.md")) else None
    roles = sorted(
        name
        for name in os.listdir(root)
        if os.path.isdir(os.path.join(root, name)) and _is_role_dir(root, name)
    )
    return Corpus(shared_dir=shared_dir, role_dirs=tuple(roles))


# --------------------------------------------------------------------------- #
# manifest-aware layout resolution (Task 9: flat-layout support)
# --------------------------------------------------------------------------- #
# Where a flat instance's single always-loaded index lives, relative to root -
# same path doctor.sh's payload-sanity check uses for topology=flat instances
# (see docs/superpowers/specs/2026-07-04-toolbox-manifest-driven-doctor-design.md,
# "memory_cliff.py flat layout").
FLAT_INDEX_REL = os.path.join(".agents", "memory", "MEMORY.md")


def read_manifest_layout(root: str) -> str | None:
    """Read ``memory_layout`` from ``$root/.agents/manifest``, LENIENTLY: this is a
    linter, not the doctor, so it must not replicate doctor.sh's manifest
    validation. An absent file, an unreadable file, or a file with no
    ``memory_layout=`` line all mean the same thing here - "no signal, fall
    through to the next precedence tier" - never an error. Returns the FIRST
    ``memory_layout=`` value among non-blank, non-``#``-comment lines (flat
    ``key=value``, matching doctor.sh's own ``manifest_get``), or ``None``."""
    try:
        with open(os.path.join(root, ".agents", "manifest"), encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("memory_layout="):
            return line.split("=", 1)[1].strip()
    return None


def resolve_layout(cli_layout: str | None, root: str) -> str:
    """Precedence: ``--layout`` flag > manifest ``memory_layout`` > current role
    discovery. A manifest value other than ``roles``/``flat`` (malformed - doctor.sh's
    job to reject, not ours) is treated the same as no signal, so it can never crash
    or silently misroute this linter."""
    if cli_layout in ("roles", "flat"):
        return cli_layout
    manifest_layout = read_manifest_layout(root)
    if manifest_layout in ("roles", "flat"):
        return manifest_layout
    return "roles"


# --------------------------------------------------------------------------- #
# Effective per-session load + cliff classification
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RoleLoad:
    role: str
    rules: int
    always_lines: int
    tokens: int


def effective_load(role: str, role_m: FileMetrics, shared_m: FileMetrics) -> RoleLoad:
    return RoleLoad(
        role=role,
        rules=role_m.rules + shared_m.rules,
        always_lines=role_m.always_lines + shared_m.always_lines,
        tokens=role_m.tokens + shared_m.tokens,
    )


def classify(load: RoleLoad) -> list[str]:
    """Return breached axes in fixed order (empty list == OK / under the cliff)."""
    breached = []
    if load.rules > RULE_CLIFF:
        breached.append("rules")
    if load.always_lines > LINE_CLIFF:
        breached.append("lines")
    if load.tokens > TOKEN_CLIFF:
        breached.append("tokens")
    return breached


# --------------------------------------------------------------------------- #
# Consolidation-pass suggestion (issue #90, #87 AC3): warn-line only.
# --------------------------------------------------------------------------- #
# "Near" = any axis at >= 90% of its cliff (over the cliff is a fortiori near).
# The fraction is a design call, not a CONVENTIONS.md value: the cliffs are
# rule-of-thumb thresholds, so the warn-line fires with headroom left to act in.
NEAR_FRACTION = 0.9


def needs_consolidation(load: RoleLoad) -> bool:
    """True when any axis sits at >= NEAR_FRACTION of its cliff, including over
    it. Purely advisory - never feeds classify() or any exit code."""
    return (
        load.rules >= NEAR_FRACTION * RULE_CLIFF
        or load.always_lines >= NEAR_FRACTION * LINE_CLIFF
        or load.tokens >= NEAR_FRACTION * TOKEN_CLIFF
    )


def render_consolidation_suggestion(per_role: list[RoleLoad]) -> str | None:
    """One advisory line naming the qualifying roles and the consolidation
    pass to invoke, or None when every role is comfortably under the cliffs.
    The trigger policy is explicit-only (#87): this linter only ever *suggests*
    a pass - it must never invoke one on any code path. The pointers are
    relative paths valid in both homes (framework/ and an instance's .agents/):
    consolidate_pass.py sits in this tool's own dir, the skill doc in the
    sibling skills/ dir - named by path, not as a slash-command, because
    default instances (skills_mount=false) don't mount skills."""
    near = [rl.role for rl in per_role if needs_consolidation(rl)]
    if not near:
        return None
    return (
        f"Suggestion: {', '.join(near)} at >={int(NEAR_FRACTION * 100)}% of a size cliff - "
        "consider a consolidation pass: consolidate_pass.py (next to this tool; "
        "guide: skills/consolidate-memory/SKILL.md)."
    )


# --------------------------------------------------------------------------- #
# Ratchet: baseline I/O + comparison
# --------------------------------------------------------------------------- #
AXES = ("rules", "always_lines", "tokens")


def _zero() -> FileMetrics:
    return FileMetrics(0, 0, 0, 0)


def compute_loads(root: str) -> tuple[list[tuple[str, FileMetrics | None]], list[RoleLoad]]:
    """Read the corpus once and return (per_file, per_role). The corpus is
    discovered from on-disk topology, not hardcoded. Raises OSError/UnicodeDecodeError
    on a read/decode failure (caller -> exit 2)."""
    corpus = discover(root)
    shared_rel = f"{corpus.shared_dir}/MEMORY.md" if corpus.shared_dir else None
    shared_m = analyze_file(os.path.join(root, shared_rel)) if shared_rel else None
    shared_eff = shared_m or _zero()

    per_file: list[tuple[str, FileMetrics | None]] = [("shared", shared_m)]
    per_role: list[RoleLoad] = []
    for name in corpus.role_dirs:
        m = analyze_file(os.path.join(root, f"{name}/MEMORY.md"))
        per_file.append((name, m))
        per_role.append(effective_load(name, m or _zero(), shared_eff))
    return per_file, per_role


def compute_loads_flat(root: str) -> tuple[list[tuple[str, FileMetrics | None]], list[RoleLoad]]:
    """Flat-layout corpus: the single index file at ``FLAT_INDEX_REL`` IS the whole
    tier-1 load - flat adapters inject it in full at session start, so unlike roles
    layout there is no shared file to add and no always-section to subtract (see
    ``analyze_text``'s ``whole_file_is_always``). Reported/keyed under the fixed
    label ``"index"`` (mirrors how roles layout keys per-role rows by role name).
    A missing index is fatal (raises OSError) rather than rendered as a
    ``(missing)`` row - the whole corpus is one file, so its absence is the
    flat-layout equivalent of an unreadable root, and ``main`` already maps that to
    a clean exit 2 with a stderr message."""
    path = os.path.join(root, FLAT_INDEX_REL)
    if not os.path.isfile(path):
        raise OSError(f"flat index not found: {path}")
    m = analyze_file(path, whole_file_is_always=True)
    assert m is not None   # just confirmed isfile() above
    per_file = [("index", m)]
    per_role = [RoleLoad(role="index", rules=m.rules, always_lines=m.always_lines, tokens=m.tokens)]
    return per_file, per_role


def baseline_dict(per_role: list[RoleLoad]) -> dict:
    return {
        rl.role: {"rules": rl.rules, "always_lines": rl.always_lines, "tokens": rl.tokens}
        for rl in per_role
    }


def write_baseline(path: str, per_role: list[RoleLoad]) -> None:
    """Write the per-role effective load as the ratchet ceiling (sorted, trailing nl)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(baseline_dict(per_role), f, indent=2, sort_keys=True)
        f.write("\n")


def load_baseline(path: str) -> dict:
    """Load + shallow-validate a baseline file. OSError if missing; ValueError if
    not a JSON object (json.JSONDecodeError is a ValueError subclass)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("baseline must be a JSON object {role: {axis: n}}")
    return data


def compare_to_baseline(per_role: list[RoleLoad], baseline: dict) -> list[str]:
    """Return one 'role / axis / base->cur' string per axis that strictly EXCEEDS
    baseline. Equal or lower passes. A role/axis absent from the baseline is itself
    a failure (fail loud, never silently pass an unmeasured axis). A role present in
    the baseline but absent from ``per_role`` (deleted from disk after baselining) is
    intentionally a silent pass - the ratchet bounds growth, not presence."""
    regressions = []
    for rl in per_role:
        base = baseline.get(rl.role)
        if base is None:
            regressions.append(f"{rl.role} / (whole role) / absent from baseline")
            continue
        cur = {"rules": rl.rules, "always_lines": rl.always_lines, "tokens": rl.tokens}
        for axis in AXES:
            b = base.get(axis)
            if b is None:
                regressions.append(f"{rl.role} / {axis} / absent from baseline")
            elif cur[axis] > b:
                regressions.append(f"{rl.role} / {axis} / {b}->{cur[axis]}")
    return regressions


def render_wholefile_info(per_file) -> str:
    """Report-only second axis: each file's whole-file size. Never gates."""
    out = ["Whole-file size (report-only, non-blocking):"]
    for name, m in per_file:
        if m is None:
            out.append(f"  {name}: (missing)")
        else:
            out.append(f"  {name}: {m.file_lines} lines / ~{m.file_tokens} tokens")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _tok(n: int) -> str:
    return "~" + str(n)


# Field widths chosen so the missing-file row and the separators align exactly
# with the data rows (per-file metric span = 8+13+11+10 = 42). The AlwaysLines
# field is 13 (> its 11-char header) so the header keeps a visible gap from Rules.
_FILE_ROW = "{:<16}{:>8}{:>13}{:>11}{:>10}"
_ROLE_ROW = "{:<24}{:>8}{:>13}{:>10}"
_MISSING_SPAN = 42   # 8 + 13 + 11 + 10, matches the per-file metric columns


def render(
    per_file: list[tuple[str, FileMetrics | None]],
    per_role: list[RoleLoad],
    load_label: str = "role + shared",
) -> str:
    """Render the two report tables + threshold footer (+ the advisory
    consolidation warn-line when a role qualifies - inside render so every
    report-printing mode carries it and non-report modes structurally can't;
    it never affects exit codes). ``load_label``
    describes what "effective load" means for this layout: roles layout sums a
    role's own file with ``shared`` (the default, preserving prior wording
    byte-for-byte); flat layout has no shared file to add - the single index IS
    the load - so ``main`` passes a label reflecting that instead."""
    out = []
    out.append("Always-loaded cliff report")
    out.append("=" * 64)
    out.append("")
    out.append(_FILE_ROW.format("File", "Rules", "AlwaysLines", "File-Lines", "~Tokens"))
    out.append(_FILE_ROW.format("-" * 4, "-" * 5, "-" * 9, "-" * 10, "-" * 7))
    for name, m in per_file:
        if m is None:
            out.append("{:<16}{:>{w}}".format(name, "(missing)", w=_MISSING_SPAN))
        else:
            out.append(_FILE_ROW.format(name, m.rules, m.always_lines, m.file_lines, _tok(m.tokens)))
    out.append("")
    out.append(_ROLE_ROW.format(f"Role ({load_label})", "Rules", "AlwaysLines", "~Tokens") + "  Status")
    out.append(_ROLE_ROW.format("-" * 20, "-" * 5, "-" * 9, "-" * 7) + "  " + "-" * 24)
    for rl in per_role:
        breached = classify(rl)
        status = "OK" if not breached else f"OVER ({' / '.join(breached)})"
        out.append(_ROLE_ROW.format(rl.role, rl.rules, rl.always_lines, _tok(rl.tokens)) + "  " + status)
    out.append("")
    out.append(
        f"Thresholds: {RULE_CLIFF} rules / {LINE_CLIFF} lines / {TOKEN_CLIFF} tokens "
        f"(effective load = {load_label})."
    )
    out.append(
        "Note: counts every '## ... Always ...' section (tier-1 + any session-start / "
        "morning-routine loaders) as always-loaded; the lazy 'Reference' section is excluded."
    )
    suggestion = render_consolidation_suggestion(per_role)
    if suggestion:
        out.append("")
        out.append(suggestion)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def _discover_root() -> str:
    """Repo root = nearest ancestor of this file containing .git or .agents/.

    A marker walk instead of depth counting, so the tool resolves the right
    tree from any home (framework/tools/ in the framework repo,
    .agents/tools/ in an installed instance, a legacy scripts/ copy, or the
    user tier's ~/.agents/tools/) - a wrong root would fail silently: zero
    roles discovered lints vacuously green. Falls back to 3 levels up (the
    blessed homes' depth) when no marker exists, e.g. bare test fixtures.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    while True:
        if os.path.exists(os.path.join(d, ".git")) or os.path.isdir(
            os.path.join(d, ".agents")
        ):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.path.dirname(os.path.dirname(here))
        d = parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint each role's tier-1 (Always in effect) load vs the size budgets."
    )
    parser.add_argument(
        "--root", default=None,
        help="memory-repo root (default: auto-detect from this script's location).",
    )
    parser.add_argument(
        "--layout", choices=("roles", "flat"), default=None,
        help="corpus layout override. Default: read `memory_layout` from "
             "$root/.agents/manifest if present, else fall back to role discovery "
             "(unchanged pre-manifest behavior).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--write-baseline", default=None, metavar="FILE",
        help="write current effective per-role load to FILE as the ratchet ceiling, then exit.",
    )
    group.add_argument(
        "--baseline", default=None, metavar="FILE",
        help="ratchet mode: exit 1 if any axis exceeds the baseline in FILE.",
    )
    args = parser.parse_args(argv)
    root = args.root or _discover_root()
    layout = resolve_layout(args.layout, root)
    load_label = "the whole index file (no role/shared split)" if layout == "flat" else "role + shared"

    try:
        per_file, per_role = compute_loads_flat(root) if layout == "flat" else compute_loads(root)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"memory_cliff: error reading corpus: {exc}", file=sys.stderr)
        return 2

    if args.write_baseline:
        write_baseline(args.write_baseline, per_role)
        print(f"Wrote baseline for {len(per_role)} roles to {args.write_baseline}")
        return 0

    if args.baseline:
        try:
            baseline = load_baseline(args.baseline)
        except (OSError, ValueError) as exc:
            print(f"memory_cliff: bad baseline file: {exc}", file=sys.stderr)
            return 2
        print(render(per_file, per_role, load_label))
        print()
        print(render_wholefile_info(per_file))
        regressions = compare_to_baseline(per_role, baseline)
        if regressions:
            print()
            print("RATCHET FAILED - always-loaded load regressed vs baseline:")
            for r in regressions:
                print(f"  {r}")
            return 1
        print()
        print("Ratchet OK - no axis exceeds baseline.")
        return 0

    print(render(per_file, per_role, load_label))
    return 1 if any(classify(rl) for rl in per_role) else 0


if __name__ == "__main__":
    sys.exit(main())   # argv=None -> argparse reads sys.argv[1:]
