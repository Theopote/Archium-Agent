"""Corpus sizing targets for Visual QA calibration sample generation."""

from __future__ import annotations

CORPUS_CATEGORY_TARGETS: dict[str, int] = {
    "site_plan": 50,
    "floor_plan": 50,
    "section": 30,
    "elevation": 30,
    "diagram": 50,
    "photo": 50,
}
