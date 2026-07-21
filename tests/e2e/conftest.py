"""Pytest config for e2e acceptance tests."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_project_acceptance: Five real-project end-to-end acceptance scenarios",
    )
    config.addinivalue_line(
        "markers",
        "phase7_acceptance: Phase 7 cultural village and renovation acceptance scaffolds",
    )
    config.addinivalue_line(
        "markers",
        "phase8_artifacts: Phase 8 real-project RenderScene deliverable artifact pipelines",
    )
    config.addinivalue_line(
        "markers",
        "requires_libreoffice: Needs LibreOffice+pdftoppm or Windows PowerPoint for PPTX screenshots",
    )
