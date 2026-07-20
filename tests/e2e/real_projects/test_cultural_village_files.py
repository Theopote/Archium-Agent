"""Tests for cultural_village_001 drop-in file package."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.e2e.real_projects.loader import load_manifest, resolve_manifest_files

_MANIFEST = Path(__file__).resolve().parent / "manifests" / "cultural_village_001.json"
_FILES_ROOT = Path(__file__).resolve().parent / "files" / "cultural_village_001"


def test_cultural_village_manifest_lists_required_files() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    required = [entry for entry in payload.get("files", []) if entry.get("required")]
    assert len(required) >= 16


def test_cultural_village_drop_in_files_exist() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    paths = resolve_manifest_files(payload)
    assert len(paths) >= 16
    image_paths = [path for path in paths if path.suffix.lower() == ".png"]
    assert len(image_paths) >= 11


def test_cultural_village_files_root_layout() -> None:
    assert (_FILES_ROOT / "documents").is_dir()
    assert (_FILES_ROOT / "data").is_dir()
    assert (_FILES_ROOT / "assets").is_dir()
    assert (_FILES_ROOT / "documents" / "村落调研纪要.docx").is_file()


@pytest.mark.parametrize(
    "relative",
    [
        "documents/村落调研纪要.docx",
        "documents/文化价值研究摘要.pdf",
        "documents/文保划定说明.pdf",
        "documents/参考汇报版式.pptx",
        "data/村落基础指标.xlsx",
        "assets/01_village_aerial.png",
        "assets/11_street_section.png",
    ],
)
def test_cultural_village_key_files(relative: str) -> None:
    path = _FILES_ROOT / relative
    assert path.is_file(), f"missing {path}"


def test_cultural_village_manifest_loads() -> None:
    loaded = load_manifest(_MANIFEST)
    assert loaded.manifest.project_id == "cultural_village_001"
    assert loaded.manifest.expectations.get("requires_cultural_narrative") is True
