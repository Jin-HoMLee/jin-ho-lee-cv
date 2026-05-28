# Phase 6 — SEO + Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the live site at `https://jinholee.is-a.dev/` discoverable (sitemap + robots.txt + Search Console + Bing) and measurable (privacy-friendly GoatCounter analytics), with all secrets unset by default so dev builds remain quiet.

**Architecture:** Two passive additions to the Astro web build. (1) `@astrojs/sitemap` integration auto-emits sitemap files; a static `web/public/robots.txt` references them. (2) `BaseLayout.astro` gains three env-gated `<head>` elements (GSC + Bing verification meta tags, GoatCounter snippet). The GitHub Pages workflow passes verification codes from repo secrets and hardcodes the analytics endpoint in `pages.yml`. With no env set, builds emit zero verification/analytics — graceful no-op for dev, PRs, and forks.

**Tech Stack:** Astro 5.x, `@astrojs/sitemap`, GoatCounter (free hosted), GitHub Actions secrets.

**Spec:** [`docs/superpowers/specs/2026-05-28-phase-6-seo-analytics-design.md`](../specs/2026-05-28-phase-6-seo-analytics-design.md)

---

## File map

**Create:**

- `web/public/robots.txt` — static file allowing all crawlers, references sitemap.

**Modify:**

- `web/package.json` + `web/pnpm-lock.yaml` — add `@astrojs/sitemap` dependency.
- `web/astro.config.mjs` — register sitemap integration with i18n + OG/404 filter.
- `web/src/layouts/BaseLayout.astro` — add 3 env-gated `<head>` elements (GSC verify, Bing verify, GoatCounter script).
- `.github/workflows/pages.yml` — add `env:` block to the `Build site` step; extend the `Smoke-check build outputs` step with assertions for sitemap, robots.txt, and the 3 production head tags.

**No changes to:**

Python content layer (`scripts/`), PDF (`pdf/`), content (`content/`), tests (`tests/`), or other workflows.

---

## Branch

This work continues on `phase-6-seo-analytics` (already created, spec already committed). All tasks below commit to this branch.

---

## Task 1: Add `@astrojs/sitemap` integration

**Files:**

- Modify: `web/package.json`
- Modify: `web/pnpm-lock.yaml`
- Modify: `web/astro.config.mjs`

- [ ] **Step 1: Install the sitemap integration**

Run from repo root:

```bash
pnpm --dir web add @astrojs/sitemap
```

Expected: `package.json` gains `"@astrojs/sitemap": "^X.Y.Z"` under `dependencies`; `pnpm-lock.yaml` updates. No errors.

- [ ] **Step 2: Register the integration in `astro.config.mjs`**

Replace the file content with:

```js
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://jinholee.is-a.dev",
  base: "/",
  trailingSlash: "always",
  i18n: {
    defaultLocale: "en",
    locales: ["en", "de"],
    routing: { prefixDefaultLocale: false },
  },
  integrations: [
    sitemap({
      i18n: {
        defaultLocale: "en",
        locales: { en: "en-US", de: "de-DE" },
      },
      filter: (page) => !page.includes("/og/") && !page.includes("/404"),
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
```

The change: added `import sitemap`, added `integrations: [sitemap({...})]`.

- [ ] **Step 3: Build and verify sitemap files exist**

Run from repo root:

```bash
just web-build
test -f web/dist/sitemap-index.xml && echo "OK index" || echo "MISSING index"
test -f web/dist/sitemap-0.xml && echo "OK 0" || echo "MISSING 0"
```

Expected:

```text
OK index
OK 0
```

If `just web-build` errors with "command not found", use `pnpm --dir web build` instead.

- [ ] **Step 4: Verify the URL count**

Run:

```bash
grep -o "<url>" web/dist/sitemap-0.xml | wc -l
```

Expected: `22` — 2 homepages (`/`, `/de/`) + 10 EN project pages (`/projects/L1/` … `/projects/L5/`, `/projects/D1/` … `/projects/D3/`, `/projects/C1/`, `/projects/C2/`) + 10 DE project pages.

(Note: `grep -c` counts matching *lines* — the sitemap XML is minified to a single line, so `-c` returns 1. Use `-o | wc -l` to count occurrences.)

If the count is wrong:

- `0`: integration not registered correctly — re-check `astro.config.mjs`.
- `44` (double): `i18n` config block is duplicating routes — confirm `routing: { prefixDefaultLocale: false }` matches the sitemap `i18n.defaultLocale: "en"`.
- `24`: OG or 404 leaked through the filter — re-check the `filter:` callback.

- [ ] **Step 5: Verify sitemap-index references sitemap-0**

Run:

```bash
grep -c "sitemap-0.xml" web/dist/sitemap-index.xml
```

Expected: `1`.

- [ ] **Step 6: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml web/astro.config.mjs
git commit -m "feat(web): add @astrojs/sitemap integration

Emits sitemap-index.xml + sitemap-0.xml at build covering all
EN/DE homepages and project pages (22 URLs). Filters out OG image
routes and 404."
```

---

## Task 2: Add static `robots.txt`

**Files:**

- Create: `web/public/robots.txt`

- [ ] **Step 1: Create the file**

Write `web/public/robots.txt` with exactly this content (no extra trailing blank lines):

```text
User-agent: *
Allow: /

Sitemap: https://jinholee.is-a.dev/sitemap-index.xml
```

- [ ] **Step 2: Build and verify it lands in dist**

Run:

```bash
just web-build
test -f web/dist/robots.txt && echo "OK" || echo "MISSING"
cat web/dist/robots.txt
```

Expected: `OK`, followed by the exact file content shown above.

Astro copies `web/public/` verbatim to `web/dist/`. No config required.

- [ ] **Step 3: Commit**

```bash
git add web/public/robots.txt
git commit -m "feat(web): add robots.txt referencing sitemap

Allows all crawlers; points at sitemap-index.xml for indexing."
```

---

## Task 3: Add env-gated verification + analytics to BaseLayout

**Files:**

- Modify: `web/src/layouts/BaseLayout.astro`

- [ ] **Step 1: Add env reads in frontmatter**

In `web/src/layouts/BaseLayout.astro`, locate the frontmatter block (lines 1–31, between the two `---` markers). At the bottom of the frontmatter, immediately before the closing `---`, add:

```ts
const gscVerify = import.meta.env.PUBLIC_GSC_VERIFY;
const bingVerify = import.meta.env.PUBLIC_BING_VERIFY;
const analyticsEnabled = import.meta.env.PUBLIC_ANALYTICS_ENABLED === "true";
const analyticsEndpoint = import.meta.env.PUBLIC_ANALYTICS_ENDPOINT;
```

- [ ] **Step 2: Emit the verification meta tags**

In the `<head>` block, immediately after the existing `<meta name="description" ... />` line (currently line 37), add:

```astro
    {gscVerify && <meta name="google-site-verification" content={gscVerify} />}
    {bingVerify && <meta name="msvalidate.01" content={bingVerify} />}
```

- [ ] **Step 3: Emit the GoatCounter snippet**

In the `<head>` block, immediately before the closing `</head>` tag (currently line 58, after the existing JSON-LD `<script>`), add:

```astro
    {analyticsEnabled && analyticsEndpoint && (
      <script
        data-goatcounter={analyticsEndpoint}
        async
        src="//gc.zgo.at/count.js"
      ></script>
    )}
```

- [ ] **Step 4: Verify no env → no emissions**

Run a clean build with no env vars set:

```bash
just web-build
grep -E "(google-site-verification|msvalidate|goatcounter)" web/dist/index.html | wc -l
```

Expected: `0`.

If the count is non-zero, the conditional checks are misfiring — verify each conditional uses truthy-only emission and that env vars are unset (`echo $PUBLIC_GSC_VERIFY` should be empty).

- [ ] **Step 5: Verify env set → all three emit**

Run:

```bash
PUBLIC_GSC_VERIFY=test-gsc \
PUBLIC_BING_VERIFY=test-bing \
PUBLIC_ANALYTICS_ENABLED=true \
PUBLIC_ANALYTICS_ENDPOINT=https://example.goatcounter.com/count \
pnpm --dir web build

grep -c 'google-site-verification' web/dist/index.html
grep -c 'msvalidate.01' web/dist/index.html
grep -c 'goatcounter' web/dist/index.html
```

Expected: each grep prints `1`.

Also spot-check a project page (the tags should appear on every page since they're in BaseLayout):

```bash
grep -c 'google-site-verification' web/dist/projects/L1/index.html
```

Expected: `1`.

- [ ] **Step 6: Clean up before commit**

The env-set build leaves verification tags baked into `web/dist/`. Re-run a clean build (no env) so a casual `just web-build` after the commit doesn't leave test values lying around:

```bash
just web-build
grep -c 'test-gsc' web/dist/index.html
```

Expected: `0`.

- [ ] **Step 7: Commit**

```bash
git add web/src/layouts/BaseLayout.astro
git commit -m "feat(web): env-gated SEO verification + analytics in BaseLayout

Adds three conditional <head> emissions to BaseLayout:
- Google Search Console meta tag (PUBLIC_GSC_VERIFY)
- Bing Webmaster meta tag (PUBLIC_BING_VERIFY)
- GoatCounter analytics snippet (PUBLIC_ANALYTICS_ENABLED + _ENDPOINT)

All four env vars unset → no emissions, so dev builds and forks
do not impersonate verification or ping analytics."
```

---

## Task 4: Wire CI env + extend smoke-check

**Files:**

- Modify: `.github/workflows/pages.yml`

- [ ] **Step 1: Add `env:` block to the Build site step**

In `.github/workflows/pages.yml`, locate the `Build site` step (currently lines 56–57):

```yaml
      - name: Build site
        run: pnpm --dir web build
```

Replace with:

```yaml
      - name: Build site
        env:
          PUBLIC_GSC_VERIFY: ${{ secrets.GSC_VERIFY }}
          PUBLIC_BING_VERIFY: ${{ secrets.BING_VERIFY }}
          PUBLIC_ANALYTICS_ENABLED: "true"
          PUBLIC_ANALYTICS_ENDPOINT: "https://jinholee.goatcounter.com/count"
        run: pnpm --dir web build
```

- [ ] **Step 2: Extend the Smoke-check build outputs step**

Locate the `Smoke-check build outputs` step (currently lines 59–80). At the end of its `run:` block (just before the closing block on line 80), append these new assertions:

```bash
          # Phase 6: SEO + analytics outputs
          # Sitemap + robots.txt exist
          test -f web/dist/sitemap-index.xml
          test -f web/dist/sitemap-0.xml
          test -f web/dist/robots.txt
          # Sitemap URL count (2 homepages + 10 projects × 2 langs = 22)
          # grep -c counts matching lines; the sitemap is minified to one line,
          # so we use -o | wc -l to count occurrences instead.
          urls=$(grep -o "<url>" web/dist/sitemap-0.xml | wc -l | tr -d ' ')
          [ "$urls" -eq 22 ] || (echo "sitemap URL count: expected 22, got $urls" && exit 1)
          # robots.txt references the sitemap
          grep -q "sitemap-index.xml" web/dist/robots.txt
          # Production head tags wired (require all repo secrets to be set, so
          # this also serves as a "did the user finish setup" check on CI runs).
          # If a secret is missing, the corresponding tag won't render and this
          # step will fail with a clear message naming which one to set.
          grep -q 'google-site-verification' web/dist/index.html || (echo "Missing GSC tag — set GSC_VERIFY repo secret" && exit 1)
          grep -q 'msvalidate.01' web/dist/index.html || (echo "Missing Bing tag — set BING_VERIFY repo secret" && exit 1)
          grep -q 'goatcounter' web/dist/index.html || (echo "Missing GoatCounter snippet — check PUBLIC_ANALYTICS_ENABLED" && exit 1)
```

Indentation must match the surrounding `run: |` block. In the existing file, lines inside the heredoc start at column 11 (10 leading spaces). Copy that level exactly — `yaml.safe_load` in step 3 will catch any mismatch.

- [ ] **Step 3: Verify the yml is well-formed locally**

Run:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml'))"
```

Expected: no output (success). If yaml errors, fix the indentation.

- [ ] **Step 4: Stage but do not yet push**

Repo secrets are not yet configured. If we push this change now and the secrets are not set, the CI smoke-check on the merge-to-main run will fail at the `grep -q 'google-site-verification'` line.

**Two-path decision point** — pick one before committing:

**Path A (safer, default):** Comment out the three "Production head tags wired" `grep -q` lines for now. Land the rails in Phase 6. After the user completes the spec §6 user-side actions (Search Console + Bing + GoatCounter sign-ups, secrets added), open a tiny follow-up PR that uncomments the lines, turning the smoke-check into a regression net.

**Path B (strict):** Leave the assertions in. User must complete spec §6 user-side actions and add all three secrets **before** merging Phase 6 to main. The first deploy run is then green by construction.

For this plan we recommend **Path A** because the spec §6 setup is async (account verification can take minutes), and we don't want to gate the merge on it. To choose Path A, edit the three `grep -q 'google-site-verification' ...`, `grep -q 'msvalidate.01' ...`, and `grep -q 'goatcounter' ...` lines to be commented out with a `# TODO Phase 6 follow-up:` prefix, like:

```bash
          # TODO Phase 6 follow-up: uncomment after GSC_VERIFY/BING_VERIFY secrets are set
          # grep -q 'google-site-verification' web/dist/index.html || (echo "Missing GSC tag — set GSC_VERIFY repo secret" && exit 1)
          # grep -q 'msvalidate.01' web/dist/index.html || (echo "Missing Bing tag — set BING_VERIFY repo secret" && exit 1)
          # grep -q 'goatcounter' web/dist/index.html || (echo "Missing GoatCounter snippet — check PUBLIC_ANALYTICS_ENABLED" && exit 1)
```

Leave the `sitemap`, `sitemap-0`, `robots.txt`, URL count, and robots-references-sitemap assertions **active** — those work without any secrets.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "ci(pages): wire SEO/analytics env + extend smoke-check

Build step now pulls GSC_VERIFY and BING_VERIFY from repo secrets;
analytics flag + endpoint hardcoded (GoatCounter endpoint is public).

Smoke-check asserts sitemap-index.xml, sitemap-0.xml, robots.txt
exist, URL count is 22, and robots references the sitemap.

Head-tag assertions left commented behind a TODO until repo
secrets are configured (spec §6 user-side actions)."
```

---

## Task 5: Final local end-to-end sanity check

**Files:** None (verification only).

- [ ] **Step 1: Clean rebuild**

```bash
rm -rf web/dist web/.astro
just web-build
```

Expected: build succeeds with no warnings related to sitemap or BaseLayout.

- [ ] **Step 2: Confirm all Phase 6 outputs**

```bash
ls web/dist/sitemap-index.xml web/dist/sitemap-0.xml web/dist/robots.txt
grep -o "<url>" web/dist/sitemap-0.xml | wc -l
grep -E -c 'google-site-verification|msvalidate|goatcounter' web/dist/index.html
```

Expected:

- All three files listed.
- URL count: `22`.
- Tag grep count: `0` (no env vars set locally → clean no-op state, as designed).

- [ ] **Step 3: Confirm pre-existing Phase 5 outputs still work**

The Phase 5 smoke-checks should still pass. Run the same checks the workflow runs:

```bash
test -f web/dist/index.html
test -f web/dist/de/index.html
test -f web/dist/projects/L1/index.html
test -f web/dist/de/projects/L1/index.html
test -f web/dist/og/index-en.png
test -f web/dist/og/projects-L1-en.png
grep -q 'property="og:image"' web/dist/index.html
echo "all phase 5 smoke checks pass"
```

Expected: final line prints. No errors.

- [ ] **Step 4: Run full validation suite**

```bash
just validate
just test
just lint
```

Expected: all green. None of these directly touch the web build, but they catch regressions if any shared scripts were inadvertently affected.

- [ ] **Step 5: No commit needed**

This task is verification only. If everything green, proceed to PR.

---

## PR creation

After Task 5 completes:

- [ ] **Step 1: Push the branch**

```bash
git push -u origin phase-6-seo-analytics
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "Phase 6: SEO + privacy-friendly analytics" --body "$(cat <<'EOF'
## Summary

- Sitemap auto-generated by `@astrojs/sitemap` (22 URLs: 2 homepages + 10 projects × 2 langs).
- `robots.txt` allows crawl, references sitemap.
- `BaseLayout.astro` gains 3 env-gated head emissions: GSC verification, Bing verification, GoatCounter snippet.
- Pages workflow wires verification codes from `secrets.GSC_VERIFY` / `secrets.BING_VERIFY`; analytics endpoint hardcoded (public).
- CI smoke-check extended to assert sitemap + robots + URL count + sitemap-self-reference. Head-tag assertions left commented behind a TODO until repo secrets are configured.

Closes #19.

## Spec

[`docs/superpowers/specs/2026-05-28-phase-6-seo-analytics-design.md`](docs/superpowers/specs/2026-05-28-phase-6-seo-analytics-design.md)

## Test plan

- [ ] `just web-build` produces `web/dist/sitemap-index.xml`, `web/dist/sitemap-0.xml`, `web/dist/robots.txt`.
- [ ] `grep -c "<url>" web/dist/sitemap-0.xml` returns `22`.
- [ ] No env vars set → no verification/analytics tags in `web/dist/index.html`.
- [ ] With all 4 env vars set → all 3 tags present in every built page.
- [ ] `just validate`, `just test`, `just lint` all green.
- [ ] CI smoke-check passes on this PR's CI run.
- [ ] After merge: `https://jinholee.is-a.dev/sitemap-index.xml` resolves (200). _Verifies on merge — `pages.yml` only runs on push to main._
- [ ] After merge: `https://jinholee.is-a.dev/robots.txt` resolves (200). _Verifies on merge._
- [ ] User-side actions completed (spec §6): GSC + Bing + GoatCounter sign-ups, repo secrets set, sitemap submitted. _Verifies in follow-up PR that uncomments smoke-check head-tag assertions._

## Out of scope

- DOI links on publications — deferred to [#26](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/26).
- jobgether medium-impact editorial fixes — separate small PR after this one.
EOF
)"
```

- [ ] **Step 3: Wait for CI green, then proceed to user-side actions**

After CI passes and the PR is opened, proceed with the spec §6 user-side actions sequence (GoatCounter sign-up → GSC property creation → Bing → repo secrets → merge). Then open the small follow-up PR that uncomments the three head-tag smoke-check assertions.

---

## Self-review checklist

Before declaring the plan complete, the author should verify:

- [ ] Every spec section §1–§9 has at least one corresponding task or explicit out-of-scope acknowledgment.
- [ ] No `TODO`, `TBD`, "implement later", or "similar to Task N" placeholders in the plan body (the one TODO is intentional, inside the commented-out smoke-check lines).
- [ ] All file paths are exact and resolvable from repo root.
- [ ] Type / property names referenced in later tasks match those defined earlier (`PUBLIC_GSC_VERIFY`, `PUBLIC_BING_VERIFY`, `PUBLIC_ANALYTICS_ENABLED`, `PUBLIC_ANALYTICS_ENDPOINT` used consistently).
- [ ] All verification commands have copy-pasteable expected output.
- [ ] Branch already exists (`phase-6-seo-analytics`) and spec already committed.
