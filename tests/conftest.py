"""Shared pytest fixtures."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "schema" / "cv.schema.json"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
REAL_PRIVATE_YAML = REPO_ROOT / "content.private" / "private.yaml"


@pytest.fixture(scope="session", autouse=True)
def real_private_yaml_guard():
    """Fail the session if any test mutates the real content.private/private.yaml.

    The real private overlay is user PII outside git's protection — a test that
    overwrites or deletes it destroys data irrecoverably (issue #77). This guard
    makes any such regression loud.
    """
    before = REAL_PRIVATE_YAML.read_bytes() if REAL_PRIVATE_YAML.exists() else None
    yield
    after = REAL_PRIVATE_YAML.read_bytes() if REAL_PRIVATE_YAML.exists() else None
    if after != before:
        raise AssertionError(
            "A test mutated the real content.private/private.yaml during this session. "
            "Tests must only ever write private overlays under tmp_path (issue #77)."
        )


@pytest.fixture
def private_leak_check():
    """Safe replacement for the old marker-overlay PII tests (issue #77).

    Calls `run_main(output_path)` and asserts no private-overlay value surfaces
    in the output file. When the real private.yaml exists it is used READ-ONLY
    (assert its guarded values don't leak); only when absent is a temporary
    marker overlay planted at the real path and removed again afterwards.
    """

    def check(run_main, output_path: Path) -> None:
        if REAL_PRIVATE_YAML.exists():
            from ruamel.yaml import YAML

            data = YAML(typ="safe").load(REAL_PRIVATE_YAML.read_text(encoding="utf-8")) or {}
            address = data.get("address") or {}
            values = [data.get("phone"), address.get("street"), address.get("postal_code")]
            guarded = [str(v).strip() for v in values if v]
            run_main(output_path)
            text = output_path.read_text()
            for value in guarded:
                if value in text:  # never echo the value via a failing assert
                    pytest.fail(f"PII leaked: a private overlay value reached {output_path.name}")
        else:
            marker_phone = "+49-555-PYTEST-MARKER"
            marker_street = "Pytest-Marker-Strasse 99"
            created_dir = not REAL_PRIVATE_YAML.parent.exists()
            REAL_PRIVATE_YAML.parent.mkdir(exist_ok=True)
            # Top-level keys, matching content.private.example/ — content_loader
            # deep_merges the file into personal, so a `personal:` root would
            # land at personal['personal'] and never be read (vacuous test).
            REAL_PRIVATE_YAML.write_text(
                f"phone: '{marker_phone}'\naddress:\n  street: '{marker_street}'\n",
                encoding="utf-8",
            )
            try:
                run_main(output_path)
                text = output_path.read_text()
                assert marker_phone not in text, f"PII leaked into {output_path.name}"
                assert marker_street not in text, f"PII leaked into {output_path.name}"
            finally:
                REAL_PRIVATE_YAML.unlink(missing_ok=True)
                if created_dir:
                    REAL_PRIVATE_YAML.parent.rmdir()

    return check


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def content_dir() -> Path:
    return CONTENT_DIR


@pytest.fixture
def schema_path() -> Path:
    return SCHEMA_PATH


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
