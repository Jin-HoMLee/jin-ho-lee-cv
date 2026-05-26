"""Assert the Python and TypeScript site-config constants stay in sync."""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
TS_PATH = REPO_ROOT / "web" / "src" / "lib" / "site-config.ts"


def _extract(ts_source: str, name: str) -> str:
    """Pull a string-literal constant out of the TS file."""
    m = re.search(rf'export const {name} = "([^"]*)"', ts_source)
    assert m, f"could not find `export const {name} = \"...\"` in {TS_PATH}"
    return m.group(1)


def test_site_domain_matches():
    from scripts.config import SITE_DOMAIN
    ts = TS_PATH.read_text()
    assert _extract(ts, "SITE_DOMAIN") == SITE_DOMAIN


def test_site_path_matches():
    from scripts.config import SITE_PATH
    ts = TS_PATH.read_text()
    assert _extract(ts, "SITE_PATH") == SITE_PATH
