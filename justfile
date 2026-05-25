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

# Build the public PDF (no PII) → dist/cv-en.pdf
build:
    uv run python -m pdf.build --lang en

# Build the private PDF (with phone + address) → dist-private/cv-en.pdf
build-private:
    uv run python -m pdf.build --lang en --private

# Build the public DE PDF (no PII) → dist/cv-de.pdf
build-de:
    uv run python -m pdf.build --lang de

# Build the private DE PDF (with phone + address) → dist-private/cv-de.pdf
build-private-de:
    uv run python -m pdf.build --lang de --private

# Render JSON for the Astro site → web/src/data/content.{en,de}.json
web-data:
    uv run python -m scripts.render_web_data

# Run the Astro dev server (regenerates data first)
web-dev: web-data
    pnpm --dir web dev

# Build the static site → web/dist/
web-build: web-data
    pnpm --dir web install --frozen-lockfile
    pnpm --dir web build

# Remove web build artifacts
web-clean:
    rm -rf web/dist web/node_modules web/src/data/*.json

# Remove build outputs (PDF + web)
clean: web-clean
    rm -rf dist/ dist-private/ pdf/.cache/
