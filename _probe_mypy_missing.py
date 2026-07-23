"""Probe mypy missing imports with ignore_missing_imports=false."""

from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

ini = textwrap.dedent(
    """
    [mypy]
    python_version = 3.11
    warn_return_any = True
    warn_unused_ignores = True
    disallow_untyped_defs = True
    check_untyped_defs = True
    ignore_missing_imports = False
    packages = archium

    [mypy-chromadb]
    follow_imports = skip
    [mypy-chromadb.*]
    follow_imports = skip
    [mypy-numpy]
    follow_imports = skip
    [mypy-numpy.*]
    follow_imports = skip
    """
).strip()
path = Path("_mypy_probe.ini")
path.write_text(ini + "\n", encoding="utf-8")
try:
    result = subprocess.run(
        [
            "py",
            "-3",
            "-m",
            "mypy",
            "archium",
            "--config-file",
            str(path),
            "--python-version",
            "3.12",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    mods: set[str] = set()
    for line in (result.stdout or "").splitlines():
        match = re.search(
            r'Cannot find implementation or library stub for module named "([^"]+)"',
            line,
        )
        if match:
            mods.add(match.group(1).split(".", 1)[0])
        match = re.search(
            r'Skipping analyzing "([^"]+)": module is installed, but missing library stubs',
            line,
        )
        if match:
            mods.add(match.group(1).split(".", 1)[0])
        match = re.search(r'Library stubs not installed for "([^"]+)"', line)
        if match:
            mods.add(match.group(1).split(".", 1)[0])
    print("EXIT", result.returncode)
    print("MISSING_ROOTS", sorted(mods))
    errors = [
        line
        for line in (result.stdout or "").splitlines()
        if ": error:" in line and "library stub" not in line.lower() and "Cannot find" not in line
    ]
    print("OTHER_ERROR_COUNT", len(errors))
    for line in errors[:20]:
        print(line)
finally:
    path.unlink(missing_ok=True)
