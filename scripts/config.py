"""Site-wide URL constants. One place to flip the canonical site URL.

These constants are mirrored in web/src/lib/site-config.ts; parity is
asserted by tests/test_config_parity.py. To re-point the site at a different
domain, edit this file + the TS mirror + web/astro.config.mjs + web/public/CNAME.
"""
from __future__ import annotations

SITE_DOMAIN: str = "cv.jinholee.com"  # bare host
SITE_PATH: str = ""                     # leading slash, no trailing slash; "" for root-served domains
PAGES_BASE_URL: str = f"https://{SITE_DOMAIN}{SITE_PATH}"
