"""Static two-tier boundary guard (Phase 14, issue #113).

Companion to tests/test_static_facts.py's DYNAMIC deep-tier check (which builds
the site with MASTER_CV_DIR pointed at master-cv.example/ and greps the output
for overlay sentinels). This test is STATIC: it proves the web-facing renderer
modules never even import - directly or transitively - the code that knows how
to read the master-cv/ overlay (scripts.master_cv_loader, scripts.profile_union).
An import that never happens can never leak data, regardless of what MASTER_CV_DIR
is set to or whether the dynamic build-and-grep guard is ever run at all.

Runs in a fresh subprocess per module (never the current pytest process, which
may have already imported scripts.master_cv_loader elsewhere in the same
session via test_render_chat_context.py / test_render_master_cv.py) so
`sys.modules` reflects exactly what importing that one module pulls in.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The web pipeline: content_loader feeds render_web_data (Astro's content JSON),
# render_jsonld (schema.org Person graph) and render_llms (the /llms.txt site map)
# - every renderer whose output reaches the crawler-facing static site. llms.txt is
# an inert AEO lever (no vendor consumes it), but it IS served publicly, so it sits
# on the same side of the two-tier boundary as the rest.
WEB_MODULES = [
    "scripts.content_loader",
    "scripts.render_web_data",
    "scripts.render_jsonld",
    "scripts.render_llms",
]

# Modules that know how to read the twin-exclusive master-cv/ overlay. Neither
# may ever appear on the web pipeline's import graph.
FORBIDDEN_MODULES = ("scripts.master_cv_loader", "scripts.profile_union")


def _imported_scripts_modules(module: str) -> set[str]:
    """Import `module` in a fresh subprocess; return every scripts.* module pulled in."""
    code = (
        "import sys\n"
        f"import {module}\n"
        "print(','.join(sorted(m for m in sys.modules if m.startswith('scripts.'))))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"importing {module} failed:\n{proc.stderr}"
    stdout = proc.stdout.strip()
    return set(stdout.split(",")) if stdout else set()


@pytest.mark.parametrize("module", WEB_MODULES)
def test_web_module_never_imports_the_deep_tier_loader(module):
    imported = _imported_scripts_modules(module)
    for forbidden in FORBIDDEN_MODULES:
        assert forbidden not in imported, (
            f"{module} transitively imports {forbidden} - the master-cv/ overlay "
            f"loader must stay unreachable from the public web pipeline. "
            f"full import graph: {sorted(imported)}"
        )


def test_forbidden_modules_are_actually_importable():
    """Sanity check on the check itself: FORBIDDEN_MODULES must be real, importable
    module names, or the assertions above would vacuously pass for a typo'd name."""
    for forbidden in FORBIDDEN_MODULES:
        imported = _imported_scripts_modules(forbidden)
        assert forbidden in imported, f"{forbidden!r} is not a real importable module"
