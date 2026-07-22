# Run the validation suite
validate:
    uv run python -m scripts.validate

# Run unit tests
test:
    uv run pytest -v

# Run lint
lint:
    uv run ruff check .

# Format
fmt:
    uv run ruff format .

# Scan staged files for PII leaks (content.private values + gitignored PII paths)
check-pii:
    uv run python -m scripts.check_pii --staged

# Activate the committed git hooks (run once per clone)
install-hooks:
    git config core.hooksPath .githooks

# Build the public PDF (no PII) → dist/cv-en.pdf
build:
    uv run python -m pdf.build --lang en

# Build the private PDF (with phone + address) → dist-private/cv-en.pdf
build-private:
    uv run python -m pdf.build --lang en --private

# Build the public DE PDF (no PII) → dist/cv-de.pdf
build-de:
    uv run python -m pdf.build --lang de

# Build a targeted PDF → dist/cv-{lang}-{target}.pdf (bridge → dist/cv-{lang}.pdf)
build-target target lang="en":
    uv run python -m pdf.build --lang {{lang}} --target {{target}}

# Build every target × lang PDF (bridge + comp-bio + ds-ml, EN + DE)
build-targets:
    uv run python -m pdf.build --lang en
    uv run python -m pdf.build --lang de
    uv run python -m pdf.build --lang en --target comp-bio
    uv run python -m pdf.build --lang de --target comp-bio
    uv run python -m pdf.build --lang en --target ds-ml
    uv run python -m pdf.build --lang de --target ds-ml

# Build the private DE PDF (with phone + address) → dist-private/cv-de.pdf
build-private-de:
    uv run python -m pdf.build --lang de --private

# Render JSON for the Astro site → web/src/data/content.{en,de}.json
web-data:
    uv run python -m scripts.render_web_data

# Render JSON Resume → dist/resume.json
build-resume:
    uv run python -m scripts.render_jsonresume

# Render schema.org JSON-LD → dist/person.jsonld
build-jsonld:
    uv run python -m scripts.render_jsonld

# Render plain text in both languages → dist/cv-{en,de}.txt
build-text:
    uv run python -m scripts.render_text --lang en
    uv run python -m scripts.render_text --lang de

# Build a targeted plain-text CV → dist/cv-{lang}-{target}.txt
build-text-target target lang="en":
    uv run python -m scripts.render_text --lang {{lang}} --target {{target}}

# Build every target × lang plain-text CV (bridge + comp-bio + ds-ml, EN + DE)
build-text-targets:
    uv run python -m scripts.render_text --lang en
    uv run python -m scripts.render_text --lang de
    uv run python -m scripts.render_text --lang en --target comp-bio
    uv run python -m scripts.render_text --lang de --target comp-bio
    uv run python -m scripts.render_text --lang en --target ds-ml
    uv run python -m scripts.render_text --lang de --target ds-ml

# Render a cover letter (validate-first) → applications/<slug>/cover-letter-*.{pdf,txt}
letter slug:
    uv run python -m scripts.render_letter "{{slug}}"

# Advisory JD↔CV keyword gap report (checklist, not a verdict) → stdout
jd-gap slug:
    uv run python -m scripts.jd_gap "{{slug}}"

# Render the llms.txt site map (llmstxt.org) → dist/llms.txt
build-llms:
    uv run python -m scripts.render_llms

# Compile the whole CV into one context blob for the digital-twin chat → dist/chat-context.md
build-chat-context:
    uv run python -m scripts.render_chat_context

# Compile the full master-CV (content/ + master-cv/ overlay) → dist/master-cv.md (lookup artifact)
build-master-cv:
    uv run python -m scripts.render_master_cv

# Run the digital-twin Worker locally (needs `cd worker && npm install` once)
worker-dev: build-chat-context
    cp dist/chat-context.md worker/chat-context.md
    cd worker && npx wrangler dev

# Deploy the digital-twin Worker (bundles a fresh chat-context.md). Needs wrangler auth + secrets set.
worker-deploy: build-chat-context
    cp dist/chat-context.md worker/chat-context.md
    cd worker && npx wrangler deploy

# Build every machine format (resume.json + person.jsonld + plain text + llms.txt)
build-formats: build-resume build-jsonld build-text build-llms build-chat-context

# Refresh Crossref citation counts → data/citations.json (the ONLY networked recipe; run manually)
refresh-citations:
    uv run python -m scripts.fetch_citations

# Regenerate committed renderer golden snapshots (run after an intentional output change)
snapshots-update:
    uv run pytest tests/test_snapshots.py --snapshot-update

# Render JSON-LD and copy into web/public/ so BaseLayout's raw import resolves.
web-jsonld:
    uv run python -m scripts.render_jsonld
    cp dist/person.jsonld web/public/person.jsonld

# Render llms.txt and copy into web/public/ so the deployed site serves /llms.txt
web-llms:
    uv run python -m scripts.render_llms
    cp dist/llms.txt web/public/llms.txt

# Run the Astro dev server (regenerates data + JSON-LD + llms.txt first)
web-dev: web-data web-jsonld web-llms
    pnpm --dir web dev

# Run the web unit tests (vitest - twin widget markdown renderer incl. XSS cases)
web-test:
    pnpm --dir web install --frozen-lockfile
    pnpm --dir web test

# Build the static site → web/dist/
web-build: web-data web-jsonld web-llms
    pnpm --dir web install --frozen-lockfile
    pnpm --dir web build

# Build the site and assert the public CV facts are crawler-readable in static HTML.
# MASTER_CV_DIR points at the committed synthetic master-cv.example/ (never the real,
# gitignored master-cv/) for the render steps, so the deep-tier guard in
# tests/test_static_facts.py is a real assertion rather than a tautology - see that
# file's module docstring.
web-guard:
    MASTER_CV_DIR="{{justfile_directory()}}/master-cv.example" just web-build
    test -f web/dist/index.html
    test -f web/dist/de/index.html
    uv run pytest tests/test_faq_jsonld.py tests/test_static_facts.py tests/test_writeup_static.py tests/test_build_writeup_static.py -v

# Remove web build artifacts
web-clean:
    rm -rf web/dist web/node_modules web/src/data/*.json web/public/person.jsonld web/public/llms.txt

# Remove build outputs (PDF + web)
clean: web-clean
    rm -rf dist/ dist-private/ pdf/.cache/

# Run the CV MCP server (stdio) — point an MCP client at this
mcp-server:
    uv run --group mcp python -m scripts.mcp_server

# Launch the MCP Inspector against the server for interactive testing
mcp-dev:
    uv run --group mcp mcp dev scripts/mcp_server.py
