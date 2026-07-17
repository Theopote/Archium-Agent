"""Streamlit startup smoke test — verify app.py boots and serves health checks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.streamlit_smoke]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HEALTH_URL = "http://127.0.0.1:8501/_stcore/health"
_STARTUP_TIMEOUT_SECONDS = 45


def _wait_for_health() -> None:
    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(_HEALTH_URL, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(1)
    raise AssertionError(f"Streamlit health check failed for {_HEALTH_URL}: {last_error}")


@pytest.mark.skipif(shutil.which("streamlit") is None, reason="Streamlit not installed")
def test_streamlit_app_starts_and_serves_health(tmp_path: Path) -> None:
    database_path = tmp_path / "streamlit-smoke.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(database_path)
    env.setdefault("LLM_API_KEY", "test-smoke-key")

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless",
            "true",
            "--server.port",
            "8501",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=_PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_health()
    except AssertionError:
        output = process.stdout.read(4000) if process.stdout is not None else ""
        raise AssertionError(f"Streamlit failed to start.\n{output}") from None
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
