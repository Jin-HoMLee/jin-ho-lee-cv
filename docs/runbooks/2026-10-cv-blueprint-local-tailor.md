# Runbook: vendoring the CV blueprint into the applications repo

Decouples CV tailoring from a live CV repo checkout. The CV repo stays the sole
owner of the three general variants (bridge, comp-bio, ds-ml); the applications
repo holds a self-contained `cv-blueprint/` snapshot of those variants plus the
build/export machinery, so a per-position export runs entirely locally.

## What is vendored

`cv-blueprint/` (wiped + rebuilt each sync):

| Path | What |
|---|---|
| `.cv-sha` | the exact CV git SHA the snapshot came from |
| `content/` | the CV `content/` master (general variants only) |
| `pdf/` | Typst build machinery (`build.py`, `projection.py`, `styles.typ`, `templates/`) |
| `scripts/` | minimal subset: `export_application.py`, `content_loader.py`, `bib_loader.py`, `langstring.py`, `publications.py`, `applications_io.py`, `__init__.py` |
| `schema/application.schema.json` | the application letter contract (reference) |
| `tailoring.example.yaml` | per-position tailoring example |
| `.typstversion` | pinned Typst version |
| `.gitignore` | ignores build artifacts + PII paths |
| `README.md` | in-snapshot usage doc |

The heavy cover-letter chain (`agent_core`, `letter_lint`, `letter_text`,
`render_web_data`, `jsonschema`) is deliberately NOT vendored: the export reads
only the lightweight `applications_io.py` helpers.

## Initial sync / refresh

Run from a CV repo checkout at the ref you want to freeze (normally the default
branch `main`), pointing at the applications repo:

```bash
python -m scripts.vendor_cv_blueprint --apps-dir /path/to/applications
# or, with the usual env contract:
APPLICATIONS_DIR=/path/to/applications python -m scripts.vendor_cv_blueprint
```

The script wipes and rebuilds `cv-blueprint/` and writes a fresh `.cv-sha`.

## Building locally in the applications repo

General variants (no CV repo dependency):

```bash
cd /path/to/applications/cv-blueprint
python -m pdf.build --lang en --target bridge
python -m pdf.build --lang en --target comp-bio
python -m pdf.build --lang en --target ds-ml
# de equivalents, as needed
```

Tailored variant (reads local content + the package's `tailoring.yaml`):

```bash
cd /path/to/applications/cv-blueprint
python -m scripts.export_application <slug>
```

The export resolves the package relative to the applications repo (the
blueprint's parent), applies `<slug>/tailoring.yaml` to a temp copy of
`cv-blueprint/content/`, builds the PDF, and writes
`<slug>/attachment-manifest.yaml` recording the `.cv-sha`. Note the `-m`
invocation: running `cv-blueprint/scripts/export_application.py` directly would
leave `cv-blueprint/scripts/` (not the blueprint root) on `sys.path`, so the
`pdf`/`scripts` packages would not import.

## CI propagation (future general-CV changes)

On a schedule (or on a push to the CV repo's default branch), a CI step in the
applications repo can: clone/fetch `jin-ho-lee-cv` at `main`, run
`python -m scripts.vendor_cv_blueprint --apps-dir .`, and open a PR if
`cv-blueprint/.cv-sha` changed. The diff is then just the content update + the
SHA bump — no hand-copying.

## Keeping the existing CV-repo export path

`just export-application-cv <slug>` in the CV repo is unchanged: when
`export_application.py` runs from a CV checkout (no `.cv-sha` marker), it reads
`content/` and records the live `git rev-parse HEAD` exactly as before.
