"""Validate repository-local links in Markdown files.

Usage:
    python scripts/check_markdown_links.py
    python scripts/check_markdown_links.py docs README.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "data:", "computer://")
DEFAULT_PATHS = (Path("README.md"), Path("QUICK_START.md"), Path("CONTRIBUTING.md"), Path("docs"))


def markdown_files(paths: list[Path]) -> list[Path]:
    """Return unique Markdown files below files/directories in stable order."""
    found: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".md":
            found.add(path)
        elif path.is_dir():
            found.update(path.rglob("*.md"))
    return sorted(found)


def missing_links(path: Path) -> list[tuple[Path, str]]:
    """Return missing repository-local link targets in one Markdown file."""
    failures: list[tuple[Path, str]] = []
    content = path.read_text(encoding="utf-8")
    for match in LINK_RE.finditer(content):
        raw_target = match.group(1).strip().strip("<>")
        target = raw_target.split("#", maxsplit=1)[0]
        if not target or target.startswith(EXTERNAL_PREFIXES):
            continue
        if not (path.parent / target).exists():
            failures.append((path, raw_target))
    return failures


def check(paths: list[Path]) -> list[tuple[Path, str]]:
    """Check all Markdown files under ``paths``."""
    failures: list[tuple[Path, str]] = []
    for path in markdown_files(paths):
        failures.extend(missing_links(path))
    return failures


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    paths = [Path(arg) for arg in args] if args else list(DEFAULT_PATHS)
    failures = check(paths)
    if failures:
        for source, target in failures:
            print(f"{source.as_posix()}: missing local link target: {target}")
        print(f"Markdown link check failed: {len(failures)} missing target(s).")
        return 1
    print(f"Markdown link check passed: {len(markdown_files(paths))} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
