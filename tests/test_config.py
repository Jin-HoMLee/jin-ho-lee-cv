"""Pytest assertions for site-wide URL constants."""
from __future__ import annotations

import re


def test_site_domain_is_bare_host():
    """SITE_DOMAIN must be just the host — no scheme, no path, no trailing slash."""
    from scripts.config import SITE_DOMAIN
    assert "://" not in SITE_DOMAIN, "SITE_DOMAIN should not include a scheme"
    assert "/" not in SITE_DOMAIN, "SITE_DOMAIN should not include a path"
    assert not SITE_DOMAIN.endswith("."), "SITE_DOMAIN should not end with '.'"
    assert re.match(r"^[a-z0-9.-]+$", SITE_DOMAIN), f"unexpected chars in SITE_DOMAIN: {SITE_DOMAIN!r}"


def test_site_path_starts_with_slash_or_empty():
    """SITE_PATH is either empty (custom-domain cutover) or a leading-slash path with no trailing slash."""
    from scripts.config import SITE_PATH
    if SITE_PATH:
        assert SITE_PATH.startswith("/"), f"SITE_PATH must start with '/' (got {SITE_PATH!r})"
        assert not SITE_PATH.endswith("/"), f"SITE_PATH must not end with '/' (got {SITE_PATH!r})"


def test_pages_base_url_format():
    """PAGES_BASE_URL: https://<host>[<path>] — no trailing slash."""
    from scripts.config import PAGES_BASE_URL
    assert PAGES_BASE_URL.startswith("https://"), f"PAGES_BASE_URL must be https (got {PAGES_BASE_URL!r})"
    assert not PAGES_BASE_URL.endswith("/"), f"PAGES_BASE_URL must not end with '/' (got {PAGES_BASE_URL!r})"
