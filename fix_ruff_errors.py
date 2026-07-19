#!/usr/bin/env python3
"""Batch fix Ruff F401 errors (unused imports) in Archium test files."""

import re
from pathlib import Path

# Map of files to unused imports that need to be removed
FIXES = {
    "tests/unit/visual/test_unlock_element.py": {
        8: "RevisionSource, "  # Remove "RevisionSource, " from line 8
    },
    "tests/unit/ui/test_studio_imports.py": {
        26: "import_studio_file, "  # Remove from import list
    },
    # Add more as needed...
}

def fix_file(file_path: str, line_fixes: dict):
    """Fix unused imports in a file."""
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        return

    lines = path.read_text().splitlines(keepends=True)

    for line_num, text_to_remove in line_fixes.items():
        if line_num <= len(lines):
            lines[line_num - 1] = lines[line_num - 1].replace(text_to_remove, "")

    path.write_text("".join(lines))
    print(f"Fixed: {file_path}")

def main():
    base_dir = Path("C:/Users/navib/Desktop/development/Archium-Agent")
    for file_path, fixes in FIXES.items():
        full_path = base_dir / file_path
        fix_file(str(full_path), fixes)

if __name__ == "__main__":
    main()
