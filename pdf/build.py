"""PDF build orchestrator: load content → resolve langs → serialize JSON → compile Typst."""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings

REPO_ROOT = Path(__file__).resolve().parent.parent


def _to_serializable(obj: Any) -> Any:
    """Recursively convert dataclasses and tuples to JSON-safe structures."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_serializable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, tuple):
        return [_to_serializable(item) for item in obj]
    if isinstance(obj, list):
        return [_to_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    return obj


def prepare_data(
    content_dir: Path,
    *,
    private_path: Path | None,
    lang: str,
) -> dict[str, Any]:
    """Load content tree, merge private overlay, resolve langstrings, return flat dict."""
    raw = load_content(content_dir, private_path=private_path, lang=lang)
    resolved = resolve_langstrings(raw, lang=lang)
    return _to_serializable(resolved)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="pdf.build",
        description="Render the CV PDF via Typst.",
    )
    p.add_argument("--lang", default="en", help="Language code (default: en)")
    p.add_argument(
        "--private",
        action="store_true",
        help="Merge content.private/private.yaml; PDF lands in dist-private/",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    content_dir = REPO_ROOT / "content"
    private_path = REPO_ROOT / "content.private" / "private.yaml" if args.private else None

    if args.private and not private_path.exists():
        print(
            f"--private was given but {private_path} does not exist. "
            "Refusing to silently produce a public build.",
            file=sys.stderr,
        )
        return 2

    data = prepare_data(content_dir, private_path=private_path, lang=args.lang)

    cache_dir = REPO_ROOT / "pdf" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # Typst invocation added in Task 4.
    print(f"Wrote {cache_dir / 'data.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
