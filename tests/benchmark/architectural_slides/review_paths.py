"""Resolve benchmark human review JSON paths on disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HUMAN_VISUAL_REVIEW_FILE = "human_visual_review.json"
HUMAN_LAYOUT_REVIEW_FILE = "human_layout_review.json"
EDITABILITY_REVIEW_FILE = "editability_review.json"
LEGACY_HUMAN_REVIEW_FILE = "human_review.json"


def visual_review_json_path(case_dir: Path) -> Path | None:
    for name in (HUMAN_VISUAL_REVIEW_FILE, LEGACY_HUMAN_REVIEW_FILE):
        path = case_dir / name
        if path.is_file():
            return path
    return None


def read_visual_review_payload(case_dir: Path) -> dict[str, Any] | None:
    path = visual_review_json_path(case_dir)
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_layout_review_payload(case_dir: Path) -> dict[str, Any] | None:
    path = case_dir / HUMAN_LAYOUT_REVIEW_FILE
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_editability_review_payload(case_dir: Path) -> dict[str, Any] | None:
    path = case_dir / EDITABILITY_REVIEW_FILE
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None
