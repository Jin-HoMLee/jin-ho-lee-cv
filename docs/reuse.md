# Use This Repository for Your Own CV

This is a working personal CV repository, not a one-command template.
The software and reusable templates are available under MIT where marked in [`REUSE.toml`](../REUSE.toml), while Jin-Ho's personal data, authored prose, likeness assets, and their generated copies remain excluded.
Replace those materials rather than publishing or adapting them as your own.

## License Boundary

[`REUSE.toml`](../REUSE.toml) is the authoritative file-level license map.
It marks the software, schemas, reusable templates, build configuration, tests, and technical documentation as MIT, then overrides the personal-material paths below with `LicenseRef-All-Rights-Reserved`.
The matching license texts live under [`LICENSES/`](../LICENSES/).

The root `LICENSE` keeps the standard MIT text unmodified so GitHub and other tooling can identify the open-source portion reliably.
GitHub's MIT label is therefore a summary of that portion, not a statement that every file in the repository is MIT-licensed.

The following personal, biographical, editorial, and likeness materials are Copyright (c) 2026 Jin-Ho Lee:

- `content/`
- `web/src/pages/writeups/`
- `docs/build-post/`
- `web/public/photo.jpg`
- `web/src/assets/digital-twin-photo.png`
- `tests/__snapshots__/`
- `docs/superpowers/plans/2026-07-20-phase-15-splice-writeup.md`
- `docs/superpowers/plans/2026-07-22-build-post.md`

All rights reserved.
Those excluded materials are not available under MIT.
The snapshot and plan exclusions cover generated or embedded copies of the reserved CV and article prose.
Replace them with your own content and assets when adapting the software.

## Start With the Core

The PDF, static website, JSON Resume, JSON-LD, and plain-text renderers all consume the same public files under `content/`.
The digital twin is optional and can be left disabled while the core CV outputs work independently.

1. Fork or clone the repository.
2. Install Python 3.12, `uv`, `just`, Typst, the Node.js version recorded in `.nvmrc`, and pnpm 10 through Corepack or your package manager.
3. Replace the YAML and BibTeX files under `content/` with your own facts.
4. Preserve the schema shapes and project references, including a `refs:` key on every experience bullet.
5. Run the validation and test commands before building any output.

```bash
uv sync
just validate
just test
just lint
uv run ruff format --check .
```

Build only the outputs you need:

```bash
just build          # English PDF
just build-de       # German PDF
just web-build      # Static Astro site
just build-formats  # JSON Resume, JSON-LD, text, and chat context
```

## Replace the Personal Material

Replace the excluded paths listed in the license boundary before publishing your fork.
The write-up registry, footer link, and write-up-specific tests currently assume Jin-Ho's two articles, so update or remove those references together.
If you remove `web/src/assets/digital-twin-photo.png`, also replace or remove its static import and portrait markup in `web/src/components/DigitalTwin.astro`; deleting the image alone breaks the web build.
The public `web/public/photo.jpg` can be replaced or removed because `web/src/components/ProfileSection.astro` checks for it at build time.
Regenerate `tests/__snapshots__/` with `just snapshots-update` after replacing the CV content.
Site-specific tests are expected to fail until their asserted names, facts, links, and articles match your replacement content.

## Change the Identity and Deployment Settings

Several deployment and interface strings are still specific to this live CV.
Use this search as a checklist rather than assuming every identity value comes from YAML:

```bash
rg -n "Jin-Ho|Jin-HoMLee|jinholee\.is-a\.dev" README.md scripts web worker .github
```

At minimum, review these files:

- `scripts/config.py`
- `web/src/lib/site-config.ts`
- `web/astro.config.mjs`
- `web/public/CNAME`
- `web/src/components/CodeHero.astro`
- `web/src/layouts/BaseLayout.astro`
- `web/.env.production`
- `.github/workflows/pages.yml`
- `worker/wrangler.toml`
- `worker/src/persona.ts`
- `web/src/components/DigitalTwin.astro`

Replace the repository URLs, canonical domain, download links, allowed origin, names, and contact wording with your own values.
In `.github/workflows/pages.yml`, replace or disable `PUBLIC_ANALYTICS_ENDPOINT` so a fork never sends analytics to Jin-Ho's GoatCounter account.
Either configure your own `GSC_VERIFY` secret or remove the workflow's mandatory Google Search Console assertion before enabling Pages.

## Keep Private Data Outside Git

Public CV builds do not need a private overlay.
For a private PDF containing contact details, create the gitignored file from the committed template:

```bash
mkdir -p content.private
cp content.private.example/private.example.yaml content.private/private.yaml
```

Fill in `content.private/private.yaml`, run `just install-hooks` once, and use `just build-private` or `just build-private-de`.
Do not commit `content.private/`, `applications/`, `master-cv/`, a real photo, or a signature.

## Treat the Digital Twin as Optional Infrastructure

The static site hides the chat widget when `PUBLIC_TWIN_ENDPOINT` is empty.
Remove or override the committed endpoint in `web/.env.production` if you only want the CV site.

Running your own twin requires your own Cloudflare Worker, KV namespace, D1 database, Turnstile configuration, model credentials, allowed origin, and persona text.
Do not reuse the account-scoped IDs in `worker/wrangler.toml` or point a fork at Jin-Ho's deployed Worker.
After creating your own resources, set `PUBLIC_TWIN_ENDPOINT` and the Turnstile site key to your deployment's public values and store all secrets through Wrangler.

## Current Limits

There is no automated rebranding command, generic content wizard, or separately maintained starter repository yet.
The guide above is the supported manual path today.
Future work can make that path more reusable without weakening the content-renderer separation that makes the project useful in the first place.
