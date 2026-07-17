"""Unit tests for PptxGenJS theme registry."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_PPTXGEN_DIR = Path(__file__).resolve().parents[2] / "archium" / "infrastructure" / "renderers" / "pptxgen"
_REQUIRED_THEMES = {
    "minimal-light",
    "minimal-dark",
    "architecture-board",
    "government-review",
    "competition",
    "technical-review",
}


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_pptxgen_theme_registry_exposes_required_themes() -> None:
    script = (
        "import { THEME_NAMES, resolveTheme } from './core/theme.mjs';"
        "const payload = { names: THEME_NAMES, sample: resolveTheme('minimal-dark').name };"
        "console.log(JSON.stringify(payload));"
    )
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=_PPTXGEN_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout.strip())
    names = set(payload["names"])
    assert names >= _REQUIRED_THEMES
    assert payload["sample"] == "minimal-dark"
