#!/usr/bin/env python3
"""Compile pinned requirement locks from pyproject.toml.

Uses ``uv`` exclusively (do not also maintain Poetry / pip-tools lock flows).

Outputs:
  requirements/base.lock          — core package dependencies only
  requirements/full-py311.lock    — ``.[full]`` resolved for CPython 3.11
  requirements/full-py312.lock    — ``.[full]`` resolved for CPython 3.12

Regenerate after changing ``[project]`` / ``[project.optional-dependencies]``::

    python scripts/compile_requirement_locks.py

Verify committed locks match pyproject (CI / pre-push)::

    python scripts/compile_requirement_locks.py --check
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
import tempfile
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


def compile_locks(
    *,
    python_versions: tuple[str, ...],
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    base_out = output_dir / "base.lock"
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
    written.append(base_out)

    for version in python_versions:
        tag = version.replace(".", "")
        out = output_dir / f"full-py{tag}.lock"
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
        written.append(out)
    return written


def check_locks(*, python_versions: tuple[str, ...]) -> int:
    """Recompile into a temp dir and fail if committed locks differ."""
    expected = ["base.lock", *[f"full-py{v.replace('.', '')}.lock" for v in python_versions]]
    missing = [name for name in expected if not (_REQ_DIR / name).is_file()]
    if missing:
        print("Missing lock files:", ", ".join(missing), file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="archium-locks-") as tmp:
        tmp_dir = Path(tmp)
        compile_locks(python_versions=python_versions, output_dir=tmp_dir)
        drift: list[str] = []
        for name in expected:
            committed = _REQ_DIR / name
            fresh = tmp_dir / name
            if not filecmp.cmp(committed, fresh, shallow=False):
                drift.append(name)
        if drift:
            print(
                "Requirement lock drift detected (pyproject.toml vs requirements/):\n  "
                + "\n  ".join(drift)
                + "\nRegenerate with: python scripts/compile_requirement_locks.py",
                file=sys.stderr,
            )
            return 1
    print("Requirement locks are in sync with pyproject.toml")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python-version",
        action="append",
        dest="python_versions",
        default=None,
        help="CPython version for full locks (repeatable). Default: 3.11 and 3.12.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed locks are out of sync with pyproject.toml.",
    )
    args = parser.parse_args(argv)
    versions = tuple(args.python_versions or ("3.11", "3.12"))
    if args.check:
        return check_locks(python_versions=versions)
    compile_locks(python_versions=versions, output_dir=_REQ_DIR)
    print(f"Wrote locks under {_REQ_DIR.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
