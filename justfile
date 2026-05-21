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

# Remove build outputs
clean:
    rm -rf dist/ dist-private/ pdf/.cache/
