"""Site-wide URL constants. One place to flip the canonical site URL.

Initial state mirrors today's github.io project-site URL. The cutover to a
custom domain (Task 14 of the Phase 5 plan) edits only this file + the Astro
config + adds CNAME — no other source changes.
"""
from __future__ import annotations

SITE_DOMAIN: str = "jin-homlee.github.io"  # bare host
SITE_PATH: str = "/jin-ho-lee-cv"           # leading slash, no trailing slash; empty string after cutover
PAGES_BASE_URL: str = f"https://{SITE_DOMAIN}{SITE_PATH}"
