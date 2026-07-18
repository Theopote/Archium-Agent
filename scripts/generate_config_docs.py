#!/usr/bin/env python3
"""Generate .env.example and docs/configuration-reference.md from Settings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_EXAMPLE = _PROJECT_ROOT / ".env.example"
_CONFIG_REFERENCE = _PROJECT_ROOT / "docs" / "configuration-reference.md"


def _write_if_changed(path: Path, content: str, *, check: bool) -> bool:
    normalized = content.replace("\r\n", "\n")
    if path.exists():
        existing = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if existing == normalized:
            return False
    if check:
        print(f"Out of date: {path.relative_to(_PROJECT_ROOT)}", file=sys.stderr)
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8", newline="\n")
    print(f"Wrote {path.relative_to(_PROJECT_ROOT)}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if generated files differ from committed copies.",
    )
    args = parser.parse_args(argv)

    from archium.config.registry import (
        render_env_example,
        render_markdown_reference,
        validate_registry,
    )

    validate_registry()
    env_content = render_env_example()
    doc_content = render_markdown_reference()

    env_changed = _write_if_changed(_ENV_EXAMPLE, env_content, check=args.check)
    doc_changed = _write_if_changed(_CONFIG_REFERENCE, doc_content, check=args.check)

    if args.check and (env_changed or doc_changed):
        print("Run: python scripts/generate_config_docs.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
