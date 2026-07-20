"""Tests for renovation_001 drop-in file package."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.e2e.real_projects.loader import load_manifest, resolve_manifest_files

_MANIFEST = Path(__file__).resolve().parent / "manifests" / "renovation_001.json"
_FILES_ROOT = Path(__file__).resolve().parent / "files" / "renovation_001"


def test_renovation_manifest_lists_required_files() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    required = [entry for entry in payload.get("files", []) if entry.get("required")]
    assert len(required) >= 16


def test_renovation_drop_in_files_exist() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    paths = resolve_manifest_files(payload)
    assert len(paths) >= 16
    image_paths = [path for path in paths if path.suffix.lower() == ".png"]
    assert len(image_paths) >= 11


def test_renovation_files_root_layout() -> None:
    assert (_FILES_ROOT / "documents").is_dir()
    assert (_FILES_ROOT / "data").is_dir()
    assert (_FILES_ROOT / "assets").is_dir()
    assert (_FILES_ROOT / "documents" / "改造任务书.docx").is_file()


@pytest.mark.parametrize(
    "relative",
    [
        "documents/改造任务书.docx",
        "documents/现状调研报告.pdf",
        "documents/结构检测摘要.pdf",
        "documents/参考汇报版式.pptx",
        "data/改造面积指标.xlsx",
        "assets/01_factory_aerial.png",
        "assets/11_roof_intervention.png",
    ],
)
def test_renovation_key_files(relative: str) -> None:
    path = _FILES_ROOT / relative
    assert path.is_file(), f"missing {path}"


def test_renovation_manifest_loads() -> None:
    loaded = load_manifest(_MANIFEST)
    assert loaded.manifest.project_id == "renovation_001"
    assert loaded.manifest.scenario.value == "existing_renovation"
