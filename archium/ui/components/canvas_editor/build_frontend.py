"""Build the Canvas Editor Streamlit custom component frontend."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_COMPONENT_ROOT = Path(__file__).resolve().parent
_FRONTEND_DIR = _COMPONENT_ROOT / "frontend"
_BUILD_DIR = _FRONTEND_DIR / "build"


def canvas_editor_build_dir(component_root: Path | None = None) -> Path:
    root = component_root or _COMPONENT_ROOT
    return root / "frontend" / "build"


def is_canvas_editor_built(component_root: Path | None = None) -> bool:
    build_dir = canvas_editor_build_dir(component_root)
    return (build_dir / "index.html").is_file()


def _resolve_npm() -> str:
    if sys.platform == "win32":
        for name in ("npm.cmd", "npm.exe"):
            found = shutil.which(name)
            if found:
                return found
    found = shutil.which("npm")
    if found is None:
        raise RuntimeError("npm is required to build the canvas editor frontend")
    return found


def _run_npm(args: list[str], *, cwd: Path) -> None:
    npm = _resolve_npm()
    subprocess.run([npm, *args], cwd=cwd, check=True)


def build_canvas_editor(*, component_root: Path | None = None, install: bool = True) -> Path:
    """Run ``npm ci`` (optional) and ``npm run build`` for the canvas editor."""
    root = component_root or _COMPONENT_ROOT
    frontend = root / "frontend"
    if not (frontend / "package.json").is_file():
        raise FileNotFoundError(f"Canvas editor package.json not found: {frontend / 'package.json'}")

    if install:
        if (frontend / "package-lock.json").is_file():
            try:
                _run_npm(["ci"], cwd=frontend)
            except subprocess.CalledProcessError:
                _run_npm(["install"], cwd=frontend)
        else:
            _run_npm(["install"], cwd=frontend)
    _run_npm(["run", "build"], cwd=frontend)

    build_dir = canvas_editor_build_dir(root)
    if not is_canvas_editor_built(root):
        raise RuntimeError(f"Canvas editor build finished but {build_dir / 'index.html'} is missing")
    return build_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Canvas Editor Streamlit component frontend")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip npm ci (assume node_modules is ready)",
    )
    args = parser.parse_args(argv)
    try:
        build_dir = build_canvas_editor(install=not args.skip_install)
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Canvas editor build failed: {exc}", file=sys.stderr)
        return 1
    print(f"Canvas editor build complete: {build_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
