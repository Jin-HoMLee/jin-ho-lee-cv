"""Stage 3 export recipe: build a tailored CV PDF for an application package.

Paired-repos handoff contract (data/cv-applications-architecture-workflow):
the CV repo owns the export recipe; the applications repo is the consumer. This
script resolves a package via the Stage 1 env contract (APPLICATIONS_DIR /
CV_ROOT/applications), reads its `cv-tailoring.md` for the target variant and
`application.yaml` for the language, builds that variant PDF with the existing
`pdf.build` (build-target) machinery, copies it into `<package>/artifacts/`, and
writes the `<package>/attachment-manifest.yaml` freeze record (§4.2).

Honesty-first: a `general-honesty-first` (or any honesty gate) declared in
`cv-tailoring.md` is recorded as `cv.content_policy` and the export still runs,
but the PDF is built from `content/` exactly as-is — this script never reads
`content/` for writing and never invents or alters honesty wording. `content/`
is only ever consumed read-only by `pdf.build.prepare_data`.

Per-position tailoring: a package may also carry a `tailoring.yaml` holding
captain-approved, position-specific wording that the export applies to a
*temporary* copy of `content/` before building (the general variants and
`content/` are never touched). Supported overrides (all with EN+DE parity):

    profile:
      <variant>:           # bridge | comp-bio | ds-ml
        tagline:
          en: "..."
          de: "..."
    projects:
      <project-id>:        # e.g. L2 → content/projects/L2.{en,de}.yaml
        outcome:
          en: "..."
          de: "..."
    experience:
      <entry-id>:          # e.g. research (id from content/experience.yaml)
        append:
          - en: "..."
            de: "..."
            refs: [L4]     # optional, default []

The override is applied verbatim (it is the captain-approved wording; the
script never invents it), and the exact applied record is written back into
`cv.tailoring` of the manifest so the export stays auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ruamel.yaml import YAML

from pdf import build as pdf_build
from scripts.cover_letter_core import (
    _atomic_write,
    _resolve_apps_dir,
    _safe_application_path,
    _sanitize_slug,
    read_application,
)

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False

# Content YAML round-trips through a dedicated instance so umlauts stay
# literal (allow_unicode) in the temp tailoring copy.
_content_yaml = YAML(typ="safe")
_content_yaml.default_flow_style = False
_content_yaml.allow_unicode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
CV_REPO_NAME = "jin-ho-lee-cv"
TARGETS = ("bridge", "comp-bio", "ds-ml")
TAILORING_FILENAME = "tailoring.yaml"
_LANGS = ("en", "de")
_TAILORING_KEYS = ("profile", "projects", "experience")

# Order matters: "honesty-first" is a substring of "general-honesty-first", so the
# more specific marker must be checked first.
_HONESTY_MARKERS = (
    "general-honesty-first",
    "honesty-first",
    "honesty-gate",
    "honesty gate",
)


# --- small, pure helpers --------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head_sha(repo_root: Path = REPO_ROOT) -> str:
    """Current HEAD commit of the CV repo (the SHA this export freezes)."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(
        timespec="seconds"
    )


def _dump_yaml(data: dict) -> str:
    buf = io.StringIO()
    _yaml.dump(data, buf)
    return buf.getvalue()


def _load_content_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return _content_yaml.load(f)


def _dump_content_yaml(path: Path, data) -> None:
    buf = io.StringIO()
    _content_yaml.dump(data, buf)
    path.write_text(buf.getvalue(), encoding="utf-8")


# --- variant + policy resolution from cv-tailoring.md ----------------------------


def parse_tailoring(text: str | None) -> dict:
    """Resolve {variant, content_policy} from a `cv-tailoring.md` body.

    Variant precedence:
      1. an explicit ``variant:`` / ``target:`` key line,
      2. a ``cv-<lang>-<target>`` token (e.g. ``cv-en-comp-bio``),
      3. a bare target token.
    Falls back to ``bridge`` when nothing matches. `content_policy` is the most
    specific honesty marker found (``general-honesty-first`` etc.), else None.
    """
    variant = "bridge"
    content_policy = None

    if text:
        lower = text.lower()

        explicit = re.search(r"^\s*(?:variant|target)\s*:\s*([a-z0-9-]+)", text, re.MULTILINE)
        if explicit and explicit.group(1) in TARGETS:
            variant = explicit.group(1)
        else:
            token = re.search(r"cv-[a-z]{2}-([a-z0-9-]+)", lower)
            if token and token.group(1) in TARGETS:
                variant = token.group(1)
            else:
                for t in ("comp-bio", "ds-ml", "bridge"):
                    if re.search(rf"\b{re.escape(t)}\b", lower):
                        variant = t
                        break

        for marker in _HONESTY_MARKERS:
            if marker in lower:
                content_policy = marker
                break

    return {"variant": variant, "content_policy": content_policy}


def _resolve_language(application: dict) -> str:
    lang = application.get("language")
    if lang not in ("en", "de"):
        raise ValueError(f"application.yaml has no valid 'language' (en|de); got {lang!r}")
    return lang


# --- per-position tailoring (tailoring.yaml) ------------------------------------


def _require_en_de(value, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context}: expected a mapping, got {type(value).__name__}")
    for lang in _LANGS:
        if lang not in value or not isinstance(value[lang], str) or not value[lang].strip():
            raise ValueError(f"{context}: missing non-empty {lang!r} string")


def _validate_langmap(value, context: str) -> None:
    """A strict {en, de} map — no other keys allowed."""
    _require_en_de(value, context)
    extra = set(value) - set(_LANGS)
    if extra:
        raise ValueError(f"{context}: unexpected key(s) {sorted(extra)}; only en/de allowed")


def _validate_bullet(value, context: str) -> None:
    """An experience bullet: {en, de} text plus an optional refs list."""
    if not isinstance(value, dict):
        raise ValueError(f"{context}: expected a bullet mapping")
    _require_en_de(value, context)
    extra = set(value) - {"en", "de", "refs"}
    if extra:
        raise ValueError(f"{context}: unexpected key(s) {sorted(extra)}; only en/de/refs allowed")
    refs = value.get("refs", [])
    if refs is not None and (
        not isinstance(refs, list) or not all(isinstance(r, str) for r in refs)
    ):
        raise ValueError(f"{context}: refs must be a list of strings")


def _validate_overrides(overrides: dict) -> None:
    if not isinstance(overrides, dict):
        raise ValueError("tailoring.yaml: expected a mapping")
    unknown = set(overrides) - set(_TAILORING_KEYS)
    if unknown:
        raise ValueError(
            f"tailoring.yaml: unknown top-level key(s) {sorted(unknown)}; "
            f"expected one of {list(_TAILORING_KEYS)}"
        )

    profile = overrides.get("profile")
    if profile is not None:
        if not isinstance(profile, dict):
            raise ValueError(
                "tailoring.yaml profile: expected a mapping of variant -> {tagline: {en, de}}"
            )
        for variant, spec in profile.items():
            if variant not in TARGETS:
                raise ValueError(
                    f"tailoring.yaml profile: unknown variant {variant!r}; expected one of {list(TARGETS)}"
                )
            if not isinstance(spec, dict):
                raise ValueError(f"tailoring.yaml profile.{variant}: expected a mapping")
            extra = set(spec) - {"tagline"}
            if extra:
                raise ValueError(
                    f"tailoring.yaml profile.{variant}: unexpected key(s) {sorted(extra)}; only 'tagline' supported"
                )
            if "tagline" in spec:
                _validate_langmap(spec["tagline"], f"tailoring.yaml profile.{variant}.tagline")

    projects = overrides.get("projects")
    if projects is not None:
        if not isinstance(projects, dict):
            raise ValueError(
                "tailoring.yaml projects: expected a mapping of project-id -> {outcome: {en, de}}"
            )
        for pid, spec in projects.items():
            if not isinstance(spec, dict):
                raise ValueError(f"tailoring.yaml projects.{pid}: expected a mapping")
            extra = set(spec) - {"outcome"}
            if extra:
                raise ValueError(
                    f"tailoring.yaml projects.{pid}: unexpected key(s) {sorted(extra)}; only 'outcome' supported"
                )
            if "outcome" in spec:
                _validate_langmap(spec["outcome"], f"tailoring.yaml projects.{pid}.outcome")

    experience = overrides.get("experience")
    if experience is not None:
        if not isinstance(experience, dict):
            raise ValueError(
                "tailoring.yaml experience: expected a mapping of entry-id -> {append: [...]}"
            )
        for entry_id, spec in experience.items():
            if not isinstance(spec, dict):
                raise ValueError(f"tailoring.yaml experience.{entry_id}: expected a mapping")
            extra = set(spec) - {"append"}
            if extra:
                raise ValueError(
                    f"tailoring.yaml experience.{entry_id}: unexpected key(s) {sorted(extra)}; only 'append' supported"
                )
            bullets = spec.get("append")
            if bullets is None:
                continue
            if not isinstance(bullets, list):
                raise ValueError(f"tailoring.yaml experience.{entry_id}.append: expected a list")
            for i, bullet in enumerate(bullets):
                _validate_bullet(bullet, f"tailoring.yaml experience.{entry_id}.append[{i}]")


def load_tailoring_overrides(package_dir: Path) -> dict:
    """Read + validate `<package>/tailoring.yaml`; returns {} when absent."""
    path = package_dir / TAILORING_FILENAME
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        overrides = _yaml.load(f)
    if overrides is None:
        return {}
    _validate_overrides(overrides)
    return overrides


def apply_overrides(src_content: Path, overrides: dict) -> tuple[Path, list[dict]]:
    """Copy `src_content` to a temp tree and apply `tailoring.yaml` overrides.

    Returns ``(temp_content_dir, applied)`` where `applied` is the audit record
    of exactly what wording was written into the copy. `content/` is never
    touched; the caller owns the temp tree and must clean it up.
    """
    tmp_root = Path(tempfile.mkdtemp(prefix="cv-tailoring-"))
    content = tmp_root / "content"
    shutil.copytree(src_content, content)
    applied: list[dict] = []

    for variant, spec in (overrides.get("profile") or {}).items():
        tagline = spec.get("tagline")
        if tagline is None:
            continue
        for lang in _LANGS:
            path = content / f"profile.{lang}.yaml"
            data = _load_content_yaml(path)
            if variant == "bridge":
                data["tagline"] = tagline[lang]
            else:
                data.setdefault("variants", {}).setdefault(variant, {})["tagline"] = tagline[lang]
            _dump_content_yaml(path, data)
        applied.append(
            {
                "kind": "profile_tagline",
                "variant": variant,
                "en": tagline["en"],
                "de": tagline["de"],
            }
        )

    for pid, spec in (overrides.get("projects") or {}).items():
        outcome = spec.get("outcome")
        if outcome is None:
            continue
        for lang in _LANGS:
            path = content / "projects" / f"{pid}.{lang}.yaml"
            if not path.is_file():
                raise ValueError(
                    f"tailoring.yaml projects.{pid}: no project file {path.name} in content/projects"
                )
            data = _load_content_yaml(path)
            data["outcome"] = outcome[lang]
            _dump_content_yaml(path, data)
        applied.append(
            {"kind": "project_outcome", "id": pid, "en": outcome["en"], "de": outcome["de"]}
        )

    experience_data = None
    for entry_id, spec in (overrides.get("experience") or {}).items():
        bullets = spec.get("append") or []
        if not bullets:
            continue
        if experience_data is None:
            experience_data = _load_content_yaml(content / "experience.yaml")
        entry = next((e for e in experience_data if e.get("id") == entry_id), None)
        if entry is None:
            raise ValueError(f"tailoring.yaml experience.{entry_id}: no such experience entry id")
        for bullet in bullets:
            new_bullet = {"en": bullet["en"], "de": bullet["de"], "refs": bullet.get("refs", [])}
            entry.setdefault("bullets", []).append(new_bullet)
            applied.append(
                {
                    "kind": "experience_bullet",
                    "entry": entry_id,
                    "en": bullet["en"],
                    "de": bullet["de"],
                    "refs": new_bullet["refs"],
                }
            )
    if experience_data is not None:
        _dump_content_yaml(content / "experience.yaml", experience_data)

    return content, applied


# --- build + stage + manifest ---------------------------------------------------


def _build_to_dist(lang: str, target: str, content_dir: Path | None = None) -> Path:
    """Build the targeted public PDF via the existing `just build-target` machinery.

    `content_dir` (when given) is a per-position tailoring temp copy of the
    content tree; the general `content/` is used otherwise. Returns the built
    path under dist/. Public build only (no --private): the attached CV variant
    is the public one; phone/address belong to the letter.
    """
    argv = ["--lang", lang, "--target", target]
    if content_dir is not None:
        argv += ["--content-dir", str(content_dir)]
    rc = pdf_build.main(argv)
    if rc != 0:
        raise RuntimeError(f"pdf.build exited {rc}")
    return REPO_ROOT / "dist" / pdf_build._pdf_filename(lang, target)


def _stage_pdf(src: Path, package_dir: Path, rel: str) -> tuple[str, str]:
    """Copy a built PDF into the package under `rel`; return (rel, sha256)."""
    dest = package_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return rel, sha256_file(dest)


def _detect_letter(package_dir: Path, lang: str) -> dict | None:
    """Return the letter section when a rendered letter PDF is present, else None."""
    pdf = package_dir / f"cover-letter-{lang}.pdf"
    if not pdf.is_file():
        return None
    return {
        "source": "draft.md",
        "pdf_path": pdf.name,
        "pdf_sha256": sha256_file(pdf),
        "rendered_at": _mtime_iso(pdf),
    }


def _submit_fields(application: dict) -> dict:
    """The four submit fields read from application.yaml where available (else null)."""
    return {
        key: application.get(key)
        for key in ("status", "status_note", "submitted_at", "confirmation_ref")
    }


def export_application_cv(slug: str, *, apps_dir: Path | None = None, build_pdf=None) -> dict:
    """Build + stage a tailored CV PDF for `slug` and write its freeze manifest.

    `build_pdf` is an injectable ``callable(lang, target, content_dir=None) ->
    Path`` returning the built PDF's path (defaults to `_build_to_dist`, the
    real Typst build). Tests pass a fake to avoid a Typst compile. `content_dir`
    is the per-position tailoring temp copy (None when no tailoring.yaml).
    """
    apps_dir = _resolve_apps_dir(apps_dir)
    slug = _sanitize_slug(slug)
    package_dir = _safe_application_path(slug, apps_dir=apps_dir)
    if not package_dir.is_dir():
        raise FileNotFoundError(f"no such application: {slug}")

    application = read_application(slug, apps_dir=apps_dir)["application"]
    if not application:
        raise FileNotFoundError(f"no application.yaml for application: {slug}")
    lang = _resolve_language(application)

    tailoring_path = package_dir / "cv-tailoring.md"
    tailoring = tailoring_path.read_text(encoding="utf-8") if tailoring_path.exists() else None
    parsed = parse_tailoring(tailoring)
    variant = parsed["variant"]
    content_policy = parsed["content_policy"]

    if content_policy:
        print(
            f"note: content_policy={content_policy} — building from content/ as-is; "
            "no wording changes",
            file=sys.stderr,
        )

    # Per-position tailoring: apply captain-approved wording to a temp content
    # copy only. `content/` and the general variants are never touched.
    overrides = load_tailoring_overrides(package_dir)
    content_dir: Path | None = None
    applied: list[dict] = []
    if overrides:
        content_dir, applied = apply_overrides(REPO_ROOT / "content", overrides)
        print(
            f"note: applied {len(applied)} tailoring override(s) from "
            f"{TAILORING_FILENAME} (captain-approved wording; content/ untouched)",
            file=sys.stderr,
        )

    build = build_pdf or _build_to_dist
    try:
        built = build(lang, variant, content_dir)
        pdf_rel, pdf_sha = _stage_pdf(
            built, package_dir, f"artifacts/{pdf_build._pdf_filename(lang, variant)}"
        )
    finally:
        if content_dir is not None:
            shutil.rmtree(content_dir.parent, ignore_errors=True)

    manifest: dict = {
        "slug": slug,
        "cv": {
            "repo": CV_REPO_NAME,
            "git_sha": git_head_sha(),
            "variant": variant,
            "lang": lang,
            "pdf_path": pdf_rel,
            "pdf_sha256": pdf_sha,
            "content_policy": content_policy,
        },
    }
    if overrides:
        manifest["cv"]["tailoring"] = {"file": TAILORING_FILENAME, "applied": applied}
    letter = _detect_letter(package_dir, lang)
    if letter is not None:
        manifest["letter"] = letter
    manifest["submit"] = _submit_fields(application)

    _atomic_write(f"{slug}/attachment-manifest.yaml", _dump_yaml(manifest), apps_dir=apps_dir)
    return manifest


# --- CLI ------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="export_application", description=__doc__)
    parser.add_argument("slug", help="Application slug (folder under applications/)")
    args = parser.parse_args(argv)

    try:
        manifest = export_application_cv(args.slug)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    cv = manifest["cv"]
    print(f"exported {cv['pdf_path']} (sha256 {cv['pdf_sha256'][:12]}…)")
    print(f"wrote applications/{args.slug}/attachment-manifest.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
