"""Cover-letter core: storage, validation, and render orchestration.

Pure Python, mirrors scripts/agent_core.py conventions. Every path / PII /
subprocess guard lives here. Reads content/ read-only (via agent_core.read_cv)
for grounding; writes ONLY into the gitignored applications/ overlay.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date as _date
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML

from scripts import agent_core, letter_text
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_web_data import _to_jsonable

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "applications"
APP_SCHEMA = REPO_ROOT / "schema" / "application.schema.json"
PROFILE_SCHEMA = REPO_ROOT / "schema" / "profile.schema.json"
CONTENT_DIR = REPO_ROOT / "content"
PRIVATE_PATH = REPO_ROOT / "content.private" / "private.yaml"

ALLOWED_SUFFIXES = {".yaml", ".md", ".txt", ".pdf"}
_GAP_DECISIONS = {"transferable", "omit", "example"}

_MONTHS = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "de": [
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ],
}


# --- path safety & low-level IO -------------------------------------------------


def _safe_application_path(rel: str, *, apps_dir: Path = APPS_DIR) -> Path:
    """Resolve an applications-relative path safely, or raise ValueError.

    Blocks absolute paths, '..'/dot segments, disallowed suffixes, symlink
    escapes, and anything resolving outside apps_dir. An empty suffix is treated
    as a slug directory and allowed.
    """
    pure = PurePosixPath(rel)
    if pure.is_absolute() or rel.startswith(("/", "\\")):
        raise ValueError(f"path must be relative to applications/: {rel!r}")
    if any(part in ("..", ".") or part.startswith(".") for part in pure.parts):
        raise ValueError(f"illegal path segment in {rel!r}")
    if pure.suffix and pure.suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"disallowed suffix in {rel!r}")
    resolved = (apps_dir / rel).resolve()
    root = apps_dir.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"path escapes applications/: {rel!r}")
    return resolved


def _sanitize_slug(raw: str) -> str:
    """Lowercase, replace non-alphanumerics with hyphens, trim. Raise if empty."""
    s = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    if not s:
        raise ValueError(f"slug is empty after sanitizing: {raw!r}")
    return s


def _atomic_write(rel: str, text: str, *, apps_dir: Path = APPS_DIR) -> Path:
    """Atomically write text to a guarded applications-relative path."""
    dst = _safe_application_path(rel, apps_dir=apps_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return dst


def _read_yaml(path: Path) -> dict:
    return _yaml.load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(rel: str, data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    buf = io.StringIO()
    _yaml.dump(data, buf)
    _atomic_write(rel, buf.getvalue(), apps_dir=apps_dir)


def _schema_errors(data: dict, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(data)
    ]


# --- profile (evergreen) --------------------------------------------------------


def read_profile(*, apps_dir: Path = APPS_DIR) -> dict:
    """Return the evergreen profile dict, or {} if absent."""
    p = apps_dir / "profile.yaml"
    return _read_yaml(p) if p.exists() else {}


def write_profile(data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    """Validate against profile.schema.json, then atomically write profile.yaml."""
    errors = _schema_errors(data, PROFILE_SCHEMA)
    if errors:
        raise ValueError("invalid profile: " + "; ".join(errors))
    _write_yaml("profile.yaml", data, apps_dir=apps_dir)


# --- applications (per-job) -----------------------------------------------------


def list_applications(*, apps_dir: Path = APPS_DIR) -> list[str]:
    """Sorted slugs (directories only, excluding dotfiles and profile.yaml)."""
    if not apps_dir.exists():
        return []
    return sorted(p.name for p in apps_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def create_application(slug: str, *, job_text: str, meta: dict, apps_dir: Path = APPS_DIR) -> str:
    """Scaffold applications/<slug>/ with job.md + application.yaml. Returns the slug.

    Refuses to overwrite an existing application. Validation of application.yaml
    is deferred to validate_application (the skill fills it in iteratively).
    """
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)
    if app_dir.exists():
        raise FileExistsError(f"application already exists: {slug}")
    app_dir.mkdir(parents=True)
    _atomic_write(f"{slug}/job.md", job_text, apps_dir=apps_dir)
    _write_yaml(f"{slug}/application.yaml", meta, apps_dir=apps_dir)
    return slug


def read_application(slug: str, *, apps_dir: Path = APPS_DIR) -> dict:
    """Bundle {application, job, interview, draft}; missing parts are None."""
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)

    def _yaml_or_none(name: str):
        f = app_dir / name
        return _read_yaml(f) if f.exists() else None

    def _text_or_none(name: str):
        f = app_dir / name
        return f.read_text(encoding="utf-8") if f.exists() else None

    return {
        "application": _yaml_or_none("application.yaml"),
        "job": _text_or_none("job.md"),
        "interview": _yaml_or_none("interview.yaml"),
        "draft": _text_or_none("draft.md"),
    }


def save_interview(slug: str, data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    """Validate-light (gap decisions) then atomically write interview.yaml."""
    for gap in data.get("gaps") or []:
        if not isinstance(gap, dict) or gap.get("decision") not in _GAP_DECISIONS:
            raise ValueError(f"invalid gap decision in {gap!r}; expected one of {_GAP_DECISIONS}")
    _write_yaml(f"{_sanitize_slug(slug)}/interview.yaml", data, apps_dir=apps_dir)


def save_draft(slug: str, body: str, *, apps_dir: Path = APPS_DIR) -> None:
    """Atomically write the editable letter body to draft.md."""
    _atomic_write(f"{_sanitize_slug(slug)}/draft.md", body, apps_dir=apps_dir)


# --- grounding & validation -----------------------------------------------------


def cv_facts(*, lang: str = "en", target: str = "bridge") -> dict:
    """The single grounding source — a PII-safe reuse of agent_core.read_cv."""
    return agent_core.read_cv(lang=lang, target=target)


def validate_application(slug: str, *, apps_dir: Path = APPS_DIR) -> dict:
    """Schema + sanity checks. Returns {'valid', 'errors', 'warnings'}."""
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)
    if not app_dir.is_dir():
        return {"valid": False, "errors": [f"no such application: {slug}"], "warnings": []}
    app_file = app_dir / "application.yaml"
    if not app_file.exists():
        return {"valid": False, "errors": ["missing application.yaml"], "warnings": []}

    data = _read_yaml(app_file)
    # ruamel parses an unquoted `date: 2026-06-03` as a datetime.date; normalize it
    # to an ISO string so it satisfies the schema's string type (and _format_date,
    # which already accepts both, renders it identically either way).
    if isinstance(data.get("date"), _date):
        data["date"] = data["date"].isoformat()
    errors = _schema_errors(data, APP_SCHEMA)
    warnings: list[str] = []

    raw_date = data.get("date")
    if isinstance(raw_date, str):
        try:
            _date.fromisoformat(raw_date)
        except ValueError:
            warnings.append(f"implausible date: {raw_date!r}")

    if not (app_dir / "draft.md").exists():
        warnings.append("no draft.md yet — nothing to render")

    interview_file = app_dir / "interview.yaml"
    if interview_file.exists():
        for gap in _read_yaml(interview_file).get("gaps") or []:
            if not isinstance(gap, dict) or gap.get("decision") not in _GAP_DECISIONS:
                val = gap.get("decision") if isinstance(gap, dict) else gap
                errors.append(f"invalid gap decision {val!r}")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


# --- rendering ------------------------------------------------------------------


def _format_date(iso: str, lang: str) -> str:
    """'June 3, 2026' (en) / '3. Juni 2026' (de). Returns str(iso) on parse failure.

    Accepts a datetime.date directly (ruamel parses unquoted YAML dates that way).
    """
    if isinstance(iso, _date):
        d = iso
    else:
        try:
            d = _date.fromisoformat(iso)
        except (ValueError, TypeError):
            return str(iso)
    months = _MONTHS.get(lang, _MONTHS["en"])
    month = months[d.month - 1]
    return f"{d.day}. {month} {d.year}" if lang == "de" else f"{month} {d.day}, {d.year}"


def _salutation(lang: str, name: str | None) -> str:
    if lang == "de":
        return f"Sehr geehrte/r {name}," if name else "Sehr geehrte Damen und Herren,"
    return f"Dear {name}," if name else "Dear Hiring Manager,"


def _closing(lang: str) -> str:
    return "Mit freundlichen Grüßen" if lang == "de" else "Sincerely,"


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]


def _signer_name() -> str:
    name = cv_facts()["personal"]["name"]
    return f"{name['given']} {name['family']}"


def _public_sender(lang: str) -> dict:
    """Public identity for the text 'full' flavor — name, email, city/country only."""
    personal = cv_facts(lang=lang)["personal"]
    loc = personal.get("location") or {}
    location_line = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x)
    return {
        "name": f"{personal['name']['given']} {personal['name']['family']}",
        "email": personal["email"],
        "location_line": location_line,
    }


def _assemble_letter(application: dict, draft: str | None, lang: str) -> dict:
    recipient = application.get("recipient")
    name = recipient.get("name") if recipient else None
    return {
        "lang": lang,
        "date_display": _format_date(application["date"], lang),
        "recipient": recipient,
        "subject": application["subject"],
        "salutation": _salutation(lang, name),
        "closing": _closing(lang),
        "signer_name": _signer_name(),
        "body_paragraphs": _split_paragraphs(draft),
    }


def _letter_personal(lang: str) -> dict:
    """Resolved personal block WITH the private address merged (PDF render only).

    This is the one place PII is intentionally merged — exactly like pdf/build.py
    --private. The output PDF is gitignored. Degrades to the public location block
    when content.private/ is absent.
    """
    private = PRIVATE_PATH if PRIVATE_PATH.exists() else None
    raw = load_content(CONTENT_DIR, private_path=private, lang=lang, target="bridge")
    resolved = resolve_langstrings(raw, lang=lang)
    return _to_jsonable(resolved["personal"])


def _render_pdf(slug: str, letter: dict, lang: str, *, apps_dir: Path) -> None:
    data = {"personal": _letter_personal(lang), "letter": letter, "lang": lang}
    cache_dir = REPO_ROOT / "pdf" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "letter.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    out = _safe_application_path(f"{slug}/cover-letter-{lang}.pdf", apps_dir=apps_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    template = REPO_ROOT / "pdf" / "templates" / "cover-letter.typ"
    has_sig = "1" if (REPO_ROOT / "assets" / "signature.png").exists() else "0"
    proc = subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            str(REPO_ROOT),
            "--input",
            f"lang={lang}",
            "--input",
            f"has-signature={has_sig}",
            str(template),
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=600,
        shell=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"typst compile failed (exit {proc.returncode}):\n{proc.stderr}")


def render_letter(slug: str, *, fmt: str = "all", apps_dir: Path = APPS_DIR) -> dict:
    """Validate-first, then render fmt in {'pdf','text','all'} into the app folder.

    PDF skips gracefully when typst is absent. Returns
    {'ok', 'errors', 'rendered': [filenames], 'skipped': [filenames]}.
    """
    if fmt not in {"pdf", "text", "all"}:
        raise ValueError(f"unknown fmt {fmt!r}; expected pdf|text|all")

    slug = _sanitize_slug(slug)
    check = validate_application(slug, apps_dir=apps_dir)
    if not check["valid"]:
        return {"ok": False, "errors": check["errors"], "rendered": [], "skipped": []}

    bundle = read_application(slug, apps_dir=apps_dir)
    lang = bundle["application"]["language"]
    letter = _assemble_letter(bundle["application"], bundle["draft"], lang)
    sender = _public_sender(lang)

    rendered: list[str] = []
    skipped: list[str] = []

    if fmt in {"text", "all"}:
        _atomic_write(
            f"{slug}/cover-letter-{lang}.txt",
            letter_text.render(letter, sender, "full"),
            apps_dir=apps_dir,
        )
        _atomic_write(
            f"{slug}/cover-letter-{lang}-body.txt",
            letter_text.render(letter, sender, "body"),
            apps_dir=apps_dir,
        )
        rendered += [f"cover-letter-{lang}.txt", f"cover-letter-{lang}-body.txt"]

    if fmt in {"pdf", "all"}:
        if shutil.which("typst") is None:
            skipped.append(f"cover-letter-{lang}.pdf")
        else:
            _render_pdf(slug, letter, lang, apps_dir=apps_dir)
            rendered.append(f"cover-letter-{lang}.pdf")

    return {"ok": True, "errors": [], "rendered": rendered, "skipped": skipped}
