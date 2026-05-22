# Design: Phase 2a — CI Release Pipeline (EN PDF)

**Date:** 2026-05-22
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Predecessor phase:** Phase 1 — PDF rendering via Typst (merged `996d07e`)

## 1. Scope

The original codified-CV spec bundled "German translations + CI release automation" into a single Phase 2. We are splitting that bundle:

- **Phase 2a (this spec):** CI release pipeline that auto-publishes a public EN PDF as a GitHub Release on every push to `main`, and uploads a PR preview artifact on every pull request.
- **Phase 2b (later):** German translations across all YAML content, plus a `cv-de.pdf` build step added to the same pipeline.

The split is safe because the langstring resolver in [`scripts/langstring.py`](../../../scripts/langstring.py) already falls back to `en` when a `de` key is missing — Phase 2a can ship an EN-only release pipeline without breaking anything, and Phase 2b only needs to add YAML content plus one extra build matrix entry.

## 2. Goal

After Phase 2a:

- Every push to `main` produces a GitHub Release tagged `cv-YYYY-MM-DD-<short-sha>` with `cv-en.pdf` attached.
- `https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf` always resolves to the newest public PDF — a stable URL the future Astro site (Phase 3) and README can link to.
- Every pull request uploads `cv-en.pdf` as a downloadable workflow artifact, so reviewers can visually verify the render before merging.

## 3. Non-goals

- **DE translations** — deferred to Phase 2b.
- **DE PDF build in CI** — deferred to Phase 2b.
- **JSON Resume, JSON-LD, plain text release artifacts** — deferred to Phase 4.
- **Astro website / custom domain** — Phase 3 / Phase 5.
- **Visual regression testing** — explicitly out of scope per the parent spec (§8).
- **Source bundle (zip of YAML) attached to releases** — not requested; Git tags already pin source.
- **Pre-release / draft release workflows** — out of scope; every `main` push is treated as a publishable CV revision.

## 4. Architecture

Single workflow file: [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) extended with a second job. No new files in `.github/workflows/`. Two jobs total:

```
ci.yml
├── validate    (existing — runs on push + pull_request)
│     uv sync → scripts.validate → pytest → ruff check
└── build-pdf   (new — runs on push + pull_request, needs: validate)
      install typst (pinned) → uv run python -m pdf.build --lang en
      ├── if pull_request: upload-artifact cv-en.pdf
      └── if push to main: action-gh-release with cv-en.pdf attached
```

Rationale for one file over splitting `release.yml` out:

- Reuses the existing `actions/checkout` + `astral-sh/setup-uv` + `uv python install` + `uv sync` steps via the job dependency.
- Smaller blast radius: one workflow to reason about, one set of triggers.
- The release step is one job step guarded by an `if:` condition, not a separate workflow. The complexity does not warrant a second file.

## 5. Detailed changes

### 5.1 `.github/workflows/ci.yml`

Existing top-level structure (triggers `push: [main]` and `pull_request: [main]`) is preserved. The existing `validate` job is unchanged. A new `build-pdf` job is added with `needs: validate` so PDF builds are skipped if validation fails.

**`build-pdf` job outline:**

1. `actions/checkout@v4`
2. `astral-sh/setup-uv@v3` (latest, matching `validate`)
3. `uv python install 3.12`
4. `uv sync --all-groups`
5. `typst-community/setup-typst@v3` with `typst-version` read from `.typstversion` (`0.14.2`)
6. `uv run python -m pdf.build --lang en` — produces `dist/cv-en.pdf`. Note: `--photo` is intentionally omitted, so the public PDF is built without a headshot (Phase 1 made `--photo` opt-in; `assets/photo.jpg` is gitignored and absent from CI runners regardless).
7. **If `github.event_name == 'pull_request'`:** `actions/upload-artifact@v4` uploading `dist/cv-en.pdf` with a retention of 30 days.
8. **If `github.event_name == 'push'` and `github.ref == 'refs/heads/main'`:** `softprops/action-gh-release@v2` with:
   - `tag_name: cv-${{ steps.meta.outputs.date }}-${{ steps.meta.outputs.short_sha }}`
   - `name: CV ${{ steps.meta.outputs.date }}`
   - `files: dist/cv-en.pdf`
   - `make_latest: true`
   - `body`: short auto-generated summary containing the triggering commit subject and a link to the commit.

A small earlier step (`id: meta`) computes `date` (`date -u +%Y-%m-%d`) and `short_sha` (`${GITHUB_SHA::7}`) once and exposes them as step outputs. This keeps the tag-name and release-name expressions readable.

**Permissions:** the workflow's top-level `permissions:` block must grant `contents: write` so that `action-gh-release` can create releases and tags. Existing `validate` job needs no permissions adjustment.

### 5.2 `.typstversion` consumption

`.typstversion` already exists (Phase 1, pinned to `0.14.2`) and is consumed by `pdf/build.py` for a runtime warning. The new CI step reads the same file and passes the value to `setup-typst`, keeping CI and local builds in lockstep. If the pinned version is ever bumped, both paths pick it up.

### 5.3 README

Add a single line near the top:

> **Latest CV:** [Download `cv-en.pdf`](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf)

This link works the moment the first release lands. No badge image dependency.

## 6. Failure modes & how they're handled

| Failure mode | Mitigation |
|---|---|
| Typst version drifts between local and CI | `.typstversion` pin consumed by both `pdf/build.py` and the `setup-typst` step. |
| Same-day pushes to `main` collide on tag name | Tag includes `<short-sha>`, guaranteeing uniqueness. |
| Release exposes PII | `--private` is never passed in CI; `content.private/` does not exist on the runner; `pdf/build.py` already refuses to silently produce a public build if `--private` is set without the file. |
| Validation fails on `main` push | `build-pdf` depends on `validate`; no release is created if validation fails. |
| PDF compile fails | `build-pdf` job fails; no release is created; the push appears in GitHub Actions as a red check. |
| `softprops/action-gh-release` is upgraded breaking | Pinned to `@v2`; major-version updates are explicit. |

## 7. Testing strategy

Phase 2a is mostly CI configuration. Two layers:

1. **Local rehearsal.** Manually run `uv run python -m pdf.build --lang en` from a clean checkout (no `content.private/`, no `assets/photo.jpg`) and confirm `dist/cv-en.pdf` is produced. This is what CI does — if it passes locally with PII/photo absent, it passes in CI.
2. **CI dry-run on a PR.** Open a draft PR against `main` containing only the workflow change. Confirm:
   - `validate` job runs and passes.
   - `build-pdf` job runs and uploads the artifact.
   - No release is created (since it's a PR, not a push).
3. **Production verification.** After merging the PR, confirm:
   - A release tagged `cv-YYYY-MM-DD-<sha>` appears on the Releases page.
   - The release is marked "Latest".
   - `releases/latest/download/cv-en.pdf` resolves and downloads the expected file.

No new pytest tests are added. The existing test suite already covers the build script's behavior.

## 8. Out-of-band dependencies

- The repo must have a remote on GitHub at `Jin-HoMLee/jin-ho-lee-cv` (or wherever) for releases to be visible. This is presumed; no action needed.
- The default `GITHUB_TOKEN` provided to Actions is sufficient for creating releases when `contents: write` is granted. No PAT or secret is required.

## 9. Migration / rollback

- **Migration:** the workflow change is additive — `validate` keeps working exactly as before. The new `build-pdf` job is independent.
- **Rollback:** delete the `build-pdf` job from `ci.yml`. Existing releases stay; no data loss.

## 10. Sequencing for Phase 2b

Phase 2b will add DE translations and a DE PDF. The minimum workflow change at that point is:

- Convert the `--lang en` step into a matrix over `[en, de]`.
- Both PDFs get uploaded as artifacts on PR and attached to the release on `main`.

No restructuring of the release step is anticipated. Phase 2a's design has been chosen to make Phase 2b a small additive change.
