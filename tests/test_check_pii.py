"""Tests for scripts.check_pii — the PII-leak guard.

All private values used here are SYNTHETIC. Never put a real guarded value in
this file — the checker scans tracked files and would (correctly) flag it.
"""

import json
from pathlib import Path

import pytest

import scripts.check_pii as check_pii
from scripts.check_pii import (
    PrivateConfigError,
    Violation,
    _is_git_commit,
    hook_decision,
    load_private_values,
    scan_files,
)

REPO_ROOT = Path(__file__).parent.parent


def _write_private(tmp_path, **over):
    """Write a synthetic content.private/private.yaml and return its path."""
    data = {
        "phone": "+49 000 0000000",
        "street": "Teststraße 1",
        "postal_code": "00000",
        "city": "Testville",
        "country": "ZZ",
    }
    data.update(over)
    p = tmp_path / "private.yaml"
    p.write_text(
        f'phone: "{data["phone"]}"\n'
        "address:\n"
        f'  street: "{data["street"]}"\n'
        f'  postal_code: "{data["postal_code"]}"\n'
        f'  city: "{data["city"]}"\n'
        f'  country: "{data["country"]}"\n',
        encoding="utf-8",
    )
    return p


# ---- load_private_values --------------------------------------------------


def test_load_private_values_extracts_guarded_keys(tmp_path):
    values = load_private_values(_write_private(tmp_path))
    assert "+49 000 0000000" in values
    assert "Teststraße 1" in values
    assert "00000" in values


def test_load_private_values_excludes_city_and_country(tmp_path):
    values = load_private_values(_write_private(tmp_path))
    assert "Testville" not in values
    assert "ZZ" not in values


def test_load_private_values_empty_when_file_absent(tmp_path):
    assert load_private_values(tmp_path / "does-not-exist.yaml") == set()


# ---- malformed private.yaml → fail-closed, never crash, never echo content ----


def _write_malformed(tmp_path):
    p = tmp_path / "private.yaml"
    # Unquoted value with stray colons → YAML ParserError (the real-world cause).
    p.write_text(
        'phone: "+49 000 0000000"\naddress:\n  street: Bad: value: here\n',
        encoding="utf-8",
    )
    return p


def test_load_private_values_raises_clean_error_on_malformed_yaml(tmp_path):
    with pytest.raises(PrivateConfigError):
        load_private_values(_write_malformed(tmp_path))


def test_malformed_error_does_not_echo_file_content(tmp_path):
    # A PII tool must never leak the offending line's value into its error text.
    try:
        load_private_values(_write_malformed(tmp_path))
    except PrivateConfigError as e:
        assert "Bad: value: here" not in str(e)
    else:  # pragma: no cover
        pytest.fail("expected PrivateConfigError")


def test_main_staged_fails_closed_on_malformed_private(monkeypatch, capsys):
    def boom():
        raise PrivateConfigError("content.private/private.yaml is malformed (line 3)")

    monkeypatch.setattr(check_pii, "run_staged_scan", boom)
    rc = check_pii.main(["--staged"])
    assert rc == 1  # blocks the commit
    err = capsys.readouterr().err
    assert "malformed" in err
    assert "Traceback" not in err  # clean message, not a stack trace


def test_main_tree_fails_closed_on_malformed_private(monkeypatch, capsys):
    def boom():
        raise PrivateConfigError("content.private/private.yaml is malformed (line 3)")

    monkeypatch.setattr(check_pii, "_tracked_files", list)  # hermetic: no real git walk
    monkeypatch.setattr(check_pii, "load_private_values", boom)
    rc = check_pii.main(["--tree"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "malformed" in err
    assert "Traceback" not in err


def test_hook_denies_when_private_config_malformed():
    def boom():
        raise PrivateConfigError("content.private/private.yaml is malformed (line 3)")

    decision = hook_decision(_stdin("git commit -m x"), scan_fn=boom)
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "malformed" in decision["hookSpecificOutput"]["permissionDecisionReason"]


# ---- scan_files: known-value scan (the "yesterday's leak" scenario) -------


def test_scan_flags_doc_containing_guarded_value():
    # A normally-tracked design doc accidentally embeds the real street.
    files = [("docs/specs/old-design.md", b"e.g. ship to Privet Drive 4, 00000 Town")]
    violations = scan_files(files, {"Privet Drive 4"})
    assert len(violations) == 1
    assert violations[0].path == "docs/specs/old-design.md"


def test_scan_does_not_echo_the_private_value():
    files = [("docs/leak.md", b"Privet Drive 4 lives here")]
    violations = scan_files(files, {"Privet Drive 4"})
    # The violation message must NOT contain the raw secret (would re-leak in logs).
    assert "Privet Drive 4" not in str(violations[0])


def test_scan_ignores_public_value_not_in_private_set():
    # City/country are excluded from private_values, so a file mentioning them is clean.
    files = [("web/header.html", b"<span>Mannheim, GER</span>")]
    violations = scan_files(files, {"Privet Drive 4"})
    assert violations == []


def test_scan_clean_content_passes():
    files = [("README.md", b"A machine-readable CV.")]
    violations = scan_files(files, {"Privet Drive 4"})
    assert violations == []


# ---- scan_files: path guard -----------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "content.private/private.yaml",
        "applications/acme/job.md",
        "assets/photo.jpg",
        "assets/photo.png",
        "assets/signature.png",
        "assets/signature.svg",
    ],
)
def test_scan_flags_pii_paths(path):
    violations = scan_files([(path, b"anything")], set())
    assert len(violations) == 1
    assert violations[0].path == path


def test_scan_allows_content_private_example():
    files = [("content.private.example/private.example.yaml", b'phone: "+49 ..."')]
    assert scan_files(files, set()) == []


def test_scan_flags_pii_path_even_when_binary():
    # Path guard must fire even when content can't be decoded.
    violations = scan_files([("assets/photo.jpg", None)], set())
    assert len(violations) == 1
    assert violations[0].path == "assets/photo.jpg"


# ---- scan_files: binary / undecodable skip --------------------------------


def test_scan_skips_undecodable_content_for_value_scan():
    files = [("data/blob.bin", b"\xff\xfe\x00\x01secret")]
    assert scan_files(files, {"secret"}) == []


def test_scan_skips_none_content_for_value_scan():
    files = [("data/huge.bin", None)]
    assert scan_files(files, {"secret"}) == []


# ---- _is_git_commit -------------------------------------------------------


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git commit -m 'x'", True),
        ("git commit --amend", True),
        ("git -c user.email=x@y.z commit -m 'x'", True),
        ("git add . && git commit -m 'x'", True),
        ("git status", False),
        ("git log --oneline", False),
        ("echo commit", False),
        ("git push origin main", False),
    ],
)
def test_is_git_commit(command, expected):
    assert _is_git_commit(command) is expected


# ---- hook_decision (PreToolUse) -------------------------------------------


def _stdin(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def test_hook_denies_commit_with_pii():
    decision = hook_decision(
        _stdin("git commit -m 'oops'"),
        scan_fn=lambda: [Violation("content.private/private.yaml", "pii path")],
    )
    out = decision["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"]


def test_hook_allows_clean_commit():
    decision = hook_decision(_stdin("git commit -m 'clean'"), scan_fn=lambda: [])
    assert decision is None


def test_hook_ignores_non_commit_command_without_scanning():
    calls = []

    def scan_fn():
        calls.append(True)
        return [Violation("x", "y")]

    decision = hook_decision(_stdin("git status"), scan_fn=scan_fn)
    assert decision is None
    assert calls == []  # must not even run the scan for non-commits


def test_hook_ignores_malformed_stdin():
    assert hook_decision("not json at all", scan_fn=lambda: [Violation("x", "y")]) is None


# ---- drift guard: the wiring must actually invoke check_pii ----------------


def test_ci_invokes_check_pii():
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "check_pii" in ci


def test_pre_commit_hook_invokes_check_pii():
    hook = (REPO_ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "check_pii" in hook


def test_master_cv_path_is_blocked():
    files = [("master-cv/timeline.yaml", b"id: x")]
    violations = scan_files(files, set())
    assert violations and violations[0].path == "master-cv/timeline.yaml"


def test_master_cv_example_is_allowed():
    files = [("master-cv.example/timeline.yaml", b"id: x")]
    assert scan_files(files, set()) == []
