"""Canvas Editor frontend build smoke test."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from archium.ui.components.canvas_editor.build_frontend import (
    build_canvas_editor,
    is_canvas_editor_built,
)
from archium.ui.components.canvas_editor.runtime import (
    canvas_editor_available,
    reset_canvas_editor_component_cache,
)

pytestmark = [pytest.mark.smoke, pytest.mark.streamlit_smoke]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_COMPONENT_ROOT = _PROJECT_ROOT / "archium" / "ui" / "components" / "canvas_editor"


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm required to build canvas editor")
def test_canvas_editor_frontend_builds() -> None:
    build_dir = build_canvas_editor(component_root=_COMPONENT_ROOT)
    assert (build_dir / "index.html").is_file()
    assert is_canvas_editor_built(_COMPONENT_ROOT)


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm required to build canvas editor")
def test_canvas_editor_build_script_entrypoint() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(_COMPONENT_ROOT / "build_frontend.py"),
            "--skip-install",
        ],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    reset_canvas_editor_component_cache()
    assert canvas_editor_available() is True
