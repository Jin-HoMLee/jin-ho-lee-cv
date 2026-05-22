# Phase 2a — CI Release Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `.github/workflows/ci.yml` so every push to `main` publishes a GitHub Release with `cv-en.pdf` attached, and every pull request uploads `cv-en.pdf` as a downloadable workflow artifact.

**Architecture:** A single new `build-pdf` job is appended to the existing `ci.yml` workflow, gated on `needs: validate`. Inside that job, two terminal steps are mutually exclusive via `if:` guards: PR runs upload an artifact; main-branch pushes create a date-and-SHA-tagged release with `make_latest: true`. No new workflow files. No new Python code. Typst is installed in CI via the same `.typstversion` pin already consumed by `pdf/build.py`.

**Tech Stack:** GitHub Actions, `astral-sh/setup-uv@v3`, `typst-community/setup-typst@v3`, `actions/upload-artifact@v4`, `softprops/action-gh-release@v2`, existing `pdf/build.py` (unchanged).

**Spec reference:** [docs/superpowers/specs/2026-05-22-phase-2a-ci-release-design.md](../specs/2026-05-22-phase-2a-ci-release-design.md)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `.github/workflows/ci.yml` | Modify | Add `build-pdf` job alongside existing `validate` job. Job-level `permissions: contents: write`. |
| `README.md` | Modify | Add "Latest CV" download link near the top, pointing at `releases/latest/download/cv-en.pdf`. |

No new files. No Python source changes. No test file changes.

---

## Pre-flight: branch setup

### Task 0: Create the phase branch

**Files:**
- None (git operation only)

- [ ] **Step 1: Confirm working tree is clean and on `main`**

Run:
```bash
git status
git branch --show-current
```
Expected: `nothing to commit, working tree clean` (except possibly `?? assets/photo.jpg`, which is untracked and stays that way). Current branch: `main`.

- [ ] **Step 2: Create and switch to `phase-2a-ci-release`**

Run:
```bash
git switch -c phase-2a-ci-release
```
Expected: `Switched to a new branch 'phase-2a-ci-release'`.

---

## Task 1: Verify local PDF build matches CI conditions

This is a smoke test, not a code change. CI will run `uv run python -m pdf.build --lang en` from a clean checkout with no `content.private/` and no `assets/photo.jpg`. We verify that command works in your local environment first, so a CI failure later won't be ambiguous.

**Files:**
- None (local verification only)

- [ ] **Step 1: Confirm `content.private/` and `assets/photo.jpg` will be ignored by the build**

The default (non-`--private`) build never reads `content.private/`, and the default (non-`--photo`) build never reads `assets/photo.jpg`. So even if these files exist locally, the command behaves as it will in CI.

Verify by reading [pdf/build.py:98](../../../pdf/build.py#L98) and [pdf/build.py:120](../../../pdf/build.py#L120) — both code paths are guarded by their respective flags.

- [ ] **Step 2: Run the exact command CI will run**

Run:
```bash
rm -rf dist/
uv run python -m pdf.build --lang en
ls -la dist/cv-en.pdf
```
Expected: `dist/cv-en.pdf` exists and is non-empty (typically ~50-150 KB). Stderr contains `Wrote dist/cv-en.pdf`.

If this fails, **stop and fix it locally before continuing** — CI will fail identically.

---

## Task 2: Add `build-pdf` job skeleton (no upload, no release yet)

This adds the new job with all setup steps and the build step, but no terminal steps. The point is to make sure typst installs cleanly and the build runs in CI before we layer on the conditional outputs.

**Files:**
- Modify: `.github/workflows/ci.yml` (append a new job)

- [ ] **Step 1: Read the current `ci.yml` to understand its exact shape**

Run:
```bash
cat .github/workflows/ci.yml
```
Expected: a single `validate` job, triggered on `push: [main]` and `pull_request: [main]`. No top-level `permissions:` block.

- [ ] **Step 2: Replace `.github/workflows/ci.yml` with the extended version**

Write the full file content below. The `validate` job is unchanged from its current contents; the only addition is the `build-pdf` job at the bottom and the new top-level `permissions:` block.

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Validate content
        run: uv run python -m scripts.validate

      - name: Run tests
        run: uv run pytest -v --tb=short

      - name: Lint
        run: uv run ruff check .

  build-pdf:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Read pinned Typst version
        id: typst-version
        run: echo "version=$(cat .typstversion)" >> "$GITHUB_OUTPUT"

      - name: Install Typst
        uses: typst-community/setup-typst@v3
        with:
          typst-version: ${{ steps.typst-version.outputs.version }}

      - name: Build EN PDF
        run: uv run python -m pdf.build --lang en
```

- [ ] **Step 3: Validate YAML syntax**

Run:
```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: no output, exit code 0. (If exit code is nonzero, fix the YAML and retry.)

- [ ] **Step 4: Commit**

Run:
```bash
git add .github/workflows/ci.yml
git commit -m "ci: add build-pdf job with typst install and EN build"
```

---

## Task 3: Add PR artifact upload

Append a step that runs only on pull requests, uploading `dist/cv-en.pdf` for reviewer download.

**Files:**
- Modify: `.github/workflows/ci.yml` (append step inside `build-pdf` job)

- [ ] **Step 1: Append the upload-artifact step**

Add the following step at the end of the `build-pdf` job's `steps:` list (after the "Build EN PDF" step). The full job will now end like this:

```yaml
      - name: Build EN PDF
        run: uv run python -m pdf.build --lang en

      - name: Upload PR preview artifact
        if: github.event_name == 'pull_request'
        uses: actions/upload-artifact@v4
        with:
          name: cv-en-pdf
          path: dist/cv-en.pdf
          retention-days: 30
          if-no-files-found: error
```

The `if-no-files-found: error` clause makes the build fail loudly if the PDF wasn't produced — better than silently uploading nothing.

- [ ] **Step 2: Validate YAML syntax**

Run:
```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

Run:
```bash
git add .github/workflows/ci.yml
git commit -m "ci: upload cv-en.pdf as PR preview artifact"
```

---

## Task 4: Add release-on-main step with date+SHA tag

Append the release step, gated on `push` events to `main`. Compute the tag components (`date`, `short_sha`) in a small meta step. Grant `contents: write` at the job level (override the read-only default).

**Files:**
- Modify: `.github/workflows/ci.yml` (add `permissions:` to job + append two steps)

- [ ] **Step 1: Add `permissions: contents: write` to the `build-pdf` job**

Just below `runs-on: ubuntu-latest` in the `build-pdf` job, add:

```yaml
  build-pdf:
    needs: validate
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
```

The top-level `permissions: contents: read` stays — it's the safe default for the `validate` job. The job-level override grants exactly the scope `action-gh-release` needs.

- [ ] **Step 2: Append the meta step and the release step**

Add these two steps at the end of the `build-pdf` job's `steps:` list (after the `Upload PR preview artifact` step):

```yaml
      - name: Compute release metadata
        id: meta
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: |
          echo "date=$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"
          echo "short_sha=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

      - name: Create GitHub Release
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: softprops/action-gh-release@v2
        with:
          tag_name: cv-${{ steps.meta.outputs.date }}-${{ steps.meta.outputs.short_sha }}
          name: CV ${{ steps.meta.outputs.date }}
          files: dist/cv-en.pdf
          make_latest: true
          body: |
            Auto-generated CV release from commit ${{ github.sha }}.

            Commit: ${{ github.event.head_commit.message }}

            View commit: ${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}
```

- [ ] **Step 3: Validate YAML syntax**

Run:
```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: no output, exit code 0.

- [ ] **Step 4: Visually inspect the full file**

Run:
```bash
cat .github/workflows/ci.yml
```

Confirm:
- Top-level `permissions: contents: read` is present.
- The `build-pdf` job has `permissions: contents: write` directly under `runs-on`.
- The `build-pdf` job's steps are in this exact order: checkout, setup-uv, python install, uv sync, read typst version, install typst, build PDF, upload artifact (PR-only), meta (main-only), release (main-only).

- [ ] **Step 5: Commit**

Run:
```bash
git add .github/workflows/ci.yml
git commit -m "ci: create GitHub Release with cv-en.pdf on push to main"
```

---

## Task 5: Update README with "Latest CV" link

Add a one-line link near the top so visitors can grab the current PDF without hunting through the Releases page.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Insert the "Latest CV" line after the project title**

Add a line directly after the title (currently line 1) and before the description paragraph. The top of `README.md` should become:

```markdown
# Jin-Ho Lee — Codified CV

**Latest CV:** [Download `cv-en.pdf`](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf) — auto-published on every change to `main`.

Machine-readable, version-controlled CV. Single source of truth in YAML + BibTeX; renderers produce PDF, website, JSON Resume, JSON-LD, and plain text.
```

Use the Edit tool with `old_string` being the current first line + the description line, and `new_string` being the same with the Latest CV line inserted between them. Match the existing markdown style — no extra blank lines.

- [ ] **Step 2: Verify the change reads well**

Run:
```bash
head -8 README.md
```
Expected: the title, then the new Latest CV line, then the existing description, then a blank line, then the next paragraph.

- [ ] **Step 3: Commit**

Run:
```bash
git add README.md
git commit -m "docs: add Latest CV download link to README"
```

---

## Task 6: Push branch and open a draft PR for integration testing

This is the first time CI will run with the new `build-pdf` job. Goal: confirm the PR path works (artifact uploaded, no release created) before merging.

**Files:**
- None (CI verification only)

- [ ] **Step 1: Push the branch**

Run:
```bash
git push -u origin phase-2a-ci-release
```
Expected: branch pushed to `origin`.

- [ ] **Step 2: Open a draft PR via gh CLI**

Run:
```bash
gh pr create --draft --title "Phase 2a: CI release pipeline" --body "$(cat <<'EOF'
## Summary

Adds a `build-pdf` job to `ci.yml` that:
- Builds `cv-en.pdf` on every PR and uploads it as a workflow artifact.
- On push to `main`, creates a GitHub Release tagged `cv-YYYY-MM-DD-<short-sha>` with `cv-en.pdf` attached and `make_latest: true`.

Implements [Phase 2a spec](docs/superpowers/specs/2026-05-22-phase-2a-ci-release-design.md).

## Test plan

- [ ] CI: validate job passes
- [ ] CI: build-pdf job passes
- [ ] CI: `cv-en-pdf` artifact attached to this PR run
- [ ] CI: NO release created (PR event, not push)
- [ ] After merge: release tagged `cv-YYYY-MM-DD-<short-sha>` appears
- [ ] After merge: release marked "Latest"
- [ ] After merge: `releases/latest/download/cv-en.pdf` resolves
EOF
)"
```
Expected: `gh pr create` returns the PR URL. If `gh` is not installed or not authenticated, fall back to the GitHub web UI.

- [ ] **Step 3: Wait for CI to complete on the PR**

Run:
```bash
gh pr checks --watch
```
Expected: both `validate` and `build-pdf` jobs succeed.

If `build-pdf` fails, read the workflow logs (`gh run view --log-failed`), fix the issue locally, commit, and push.

- [ ] **Step 4: Confirm the PR has the artifact attached**

Run:
```bash
gh run list --workflow=ci.yml --branch=phase-2a-ci-release --limit=1 --json databaseId --jq '.[0].databaseId' | xargs -I {} gh run view {} --json jobs --jq '.jobs[] | select(.name=="build-pdf") | .steps[].name'
```
Expected: the step list ends with `Upload PR preview artifact` and does NOT contain `Create GitHub Release`.

Alternatively, navigate to the workflow run in the GitHub UI and confirm the `cv-en-pdf` artifact appears in the run's "Artifacts" section.

- [ ] **Step 5: Confirm no release was created**

Run:
```bash
gh release list --limit 5
```
Expected: no release with a `cv-` prefix has been created (or the most recent release, if any, is older than this run).

---

## Task 7: Merge with `--no-ff` and verify production release

Per project convention ([CLAUDE.md](../../../CLAUDE.md)), per-phase branches merge to `main` with `--no-ff` to preserve the phase boundary in history. This task closes the phase by merging and verifying the first real release lands correctly.

**Files:**
- None (merge + verification only)

- [ ] **Step 1: Mark the PR ready for review**

Run:
```bash
gh pr ready
```

- [ ] **Step 2: Merge to `main` with `--no-ff`**

```bash
git switch main
git pull
git merge --no-ff phase-2a-ci-release -m "Merge Phase 2a: CI release pipeline"
git push origin main
```

- [ ] **Step 3: Wait for the `main`-branch CI run to complete**

Run:
```bash
gh run watch
```
Expected: both `validate` and `build-pdf` jobs succeed. The `build-pdf` job's step list now includes `Compute release metadata` and `Create GitHub Release`.

- [ ] **Step 4: Confirm the release exists and is marked latest**

Run:
```bash
gh release list --limit 3
gh release view --web
```
Expected: a release named `CV YYYY-MM-DD` with tag `cv-YYYY-MM-DD-<short-sha>` exists at the top of the list, and the web view shows the "Latest" badge.

- [ ] **Step 5: Confirm `releases/latest/download/cv-en.pdf` resolves**

Run:
```bash
curl -sLI -o /dev/null -w "%{http_code}\n" "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf"
```
Expected: `200`. (A `404` indicates the asset name didn't match or the release isn't marked latest.)

- [ ] **Step 6: Download and visually verify the published PDF**

```bash
curl -sL -o /tmp/cv-en-published.pdf "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf"
open /tmp/cv-en-published.pdf
```
Expected: identical render to your local `dist/cv-en.pdf`. One page, no photo, no PII (no phone, no street address — `Mannheim, DE` only).

- [ ] **Step 7: Delete the merged branch**

```bash
git branch -d phase-2a-ci-release
git push origin --delete phase-2a-ci-release
```

- [ ] **Step 8: Update CLAUDE.md status table**

Edit [CLAUDE.md](../../../CLAUDE.md), row 21 (`| 2 | German translations + CI release automation | Not started |`), splitting the phase into 2a (done) and 2b (not started):

```markdown
| 2a | CI release automation (EN PDF) | ✅ Done (merged YYYY-MM-DD, commit `<merge-sha>`) |
| 2b | German translations + DE PDF in CI | Not started |
```

Replace `YYYY-MM-DD` and `<merge-sha>` with the actual values from `git log --oneline -1`.

```bash
git add CLAUDE.md
git commit -m "docs: mark Phase 2a as done, split Phase 2 into 2a + 2b"
git push origin main
```

This final commit will trigger one more CI run — and one more release. That's expected behavior (the status-table update is itself a publishable change, however small). If you'd rather avoid the extra release, squash this commit with the merge commit before pushing (advanced — only if comfortable with `git reset --soft HEAD~2`).

---

## Self-review notes

This plan covers every section of the spec:

- §2 Goal (release on push, artifact on PR, stable latest URL): Tasks 3, 4, 6, 7.
- §3 Non-goals: deliberately untouched.
- §4 Architecture (single workflow, one new job): Task 2 establishes the shape; Tasks 3, 4 layer on conditionals.
- §5.1 Workflow details: Task 2 (skeleton) → Task 3 (artifact) → Task 4 (release + permissions + meta step).
- §5.2 `.typstversion` consumption: Task 2 step 2 (read into `steps.typst-version.outputs.version`).
- §5.3 README update: Task 5.
- §6 Failure modes: covered by the spec; the plan inherits them. No additional code needed.
- §7 Testing strategy: Task 1 (local rehearsal), Task 6 (CI dry-run on PR), Task 7 (production verification).
- §9 Migration/rollback: additive; no migration steps needed.
- §10 Sequencing for Phase 2b: deliberately untouched — Phase 2b gets its own spec + plan.

No placeholders. All commands, file contents, and assertions are explicit.
