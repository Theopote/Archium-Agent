#!/usr/bin/env python3
"""Compile pinned requirement locks from pyproject.toml.

Uses ``uv`` exclusively (do not also maintain Poetry / pip-tools lock flows).

Outputs:
  requirements/base.lock          — core package dependencies only
  requirements/full-py311.lock    — ``.[full]`` resolved for CPython 3.11
  requirements/full-py312.lock    — ``.[full]`` resolved for CPython 3.12

Regenerate after changing ``[project]`` / ``[project.optional-dependencies]``::

    python scripts/compile_requirement_locks.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_REQ_DIR = _ROOT / "requirements"
_PYPROJECT = _ROOT / "pyproject.toml"


def _uv_cmd() -> list[str]:
    uv = shutil.which("uv")
    if uv:
        return [uv]
    try:
        subprocess.run(
            [sys.executable, "-m", "uv", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "uv is required to compile requirement locks.\n"
            "Install once with:  pip install uv\n"
            "Then re-run:        python scripts/compile_requirement_locks.py"
        ) from exc
    return [sys.executable, "-m", "uv"]


def _run_uv(args: list[str]) -> None:
    cmd = [*_uv_cmd(), *args]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=_ROOT)


def compile_locks(*, python_versions: tuple[str, ...]) -> None:
    _REQ_DIR.mkdir(parents=True, exist_ok=True)

    base_out = _REQ_DIR / "base.lock"
    _run_uv(
        [
            "pip",
            "compile",
            str(_PYPROJECT),
            "--python-version",
            "3.11",
            "-o",
            str(base_out),
        ]
    )

    for version in python_versions:
        tag = version.replace(".", "")
        out = _REQ_DIR / f"full-py{tag}.lock"
        _run_uv(
            [
                "pip",
                "compile",
                str(_PYPROJECT),
                "--extra",
                "full",
                "--python-version",
                version,
                "-o",
                str(out),
            ]
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python-version",
        action="append",
        dest="python_versions",
        default=None,
        help="CPython version for full locks (repeatable). Default: 3.11 and 3.12.",
    )
    args = parser.parse_args(argv)
    versions = tuple(args.python_versions or ("3.11", "3.12"))
    compile_locks(python_versions=versions)
    print(f"Wrote locks under {_REQ_DIR.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
