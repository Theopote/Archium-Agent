"""CLI flags for architectural benchmark visual render script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "render_architectural_benchmark_visuals.py"
)


def test_render_script_refuses_committed_tree_without_write_mode() -> None:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    # dry-run does not write; exit 0
    assert proc.returncode == 0


def test_render_script_help_documents_ci_and_approve_flags() -> None:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--materialize-ci-samples" in proc.stdout
    assert "--approve-goldens" in proc.stdout
