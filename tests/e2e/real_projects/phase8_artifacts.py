"""Phase 8 real-project render artifact paths and checklist."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.e2e.real_projects.phase7_loader import PHASE7_PROJECT_IDS, phase7_project_root

PHASE8_PROJECT_IDS = PHASE7_PROJECT_IDS
OUTPUTS_DIRNAME = "outputs"

HARD_REQUIRED = (
    "outline_plan.json",
    "slide_specs",
    "render_scenes",
    "scene_previews",
    "presentation.pptx",
    "render_manifest.json",
    "visual_review.json",
    "editability_review.json",
)
SOFT_OPTIONAL = (
    "presentation.pdf",
    "pptx_screenshots",
)


@dataclass(frozen=True)
class Phase8ArtifactChecklist:
    project_id: str
    outputs_dir: Path
    present: dict[str, bool] = field(default_factory=dict)
    slide_spec_count: int = 0
    render_scene_count: int = 0
    scene_preview_count: int = 0
    pptx_screenshot_count: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def hard_ok(self) -> bool:
        return all(self.present.get(name, False) for name in HARD_REQUIRED)

    @property
    def counts_aligned(self) -> bool:
        return (
            self.slide_spec_count > 0
            and self.slide_spec_count == self.render_scene_count == self.scene_preview_count
        )


def phase8_outputs_dir(project_id: str) -> Path:
    return phase7_project_root(project_id) / OUTPUTS_DIRNAME


def ensure_outputs_dir(project_id: str) -> Path:
    path = phase8_outputs_dir(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def inspect_phase8_artifacts(project_id: str) -> Phase8ArtifactChecklist:
    root = phase8_outputs_dir(project_id)
    present: dict[str, bool] = {}
    notes: list[str] = []
    for name in HARD_REQUIRED + SOFT_OPTIONAL:
        target = root / name
        if name.endswith(".json") or name.endswith(".pptx") or name.endswith(".pdf"):
            present[name] = target.is_file() and target.stat().st_size > 0
        else:
            present[name] = target.is_dir() and any(target.iterdir()) if target.is_dir() else False

    slide_specs = sorted((root / "slide_specs").glob("slide_*.json")) if present.get("slide_specs") else []
    scenes = sorted((root / "render_scenes").glob("slide_*.json")) if present.get("render_scenes") else []
    previews = sorted((root / "scene_previews").glob("slide_*.png")) if present.get("scene_previews") else []
    shots = (
        sorted((root / "pptx_screenshots").glob("slide_*.png"))
        if present.get("pptx_screenshots")
        else []
    )

    if not present.get("presentation.pdf"):
        notes.append("presentation.pdf missing (LibreOffice soft-fail allowed)")
    if not present.get("pptx_screenshots"):
        notes.append("pptx_screenshots missing (LibreOffice/pdftoppm soft-fail allowed)")

    return Phase8ArtifactChecklist(
        project_id=project_id,
        outputs_dir=root,
        present=present,
        slide_spec_count=len(slide_specs),
        render_scene_count=len(scenes),
        scene_preview_count=len(previews),
        pptx_screenshot_count=len(shots),
        notes=notes,
    )


def assert_phase8_hard_artifacts(
    project_id: str,
    *,
    min_slides: int,
) -> Phase8ArtifactChecklist:
    checklist = inspect_phase8_artifacts(project_id)
    missing = [name for name in HARD_REQUIRED if not checklist.present.get(name)]
    assert not missing, f"{project_id} missing hard artifacts: {missing}"
    assert checklist.counts_aligned, (
        f"{project_id} slide artifact counts misaligned: "
        f"specs={checklist.slide_spec_count} scenes={checklist.render_scene_count} "
        f"previews={checklist.scene_preview_count}"
    )
    assert checklist.slide_spec_count >= min_slides, (
        f"{project_id} slide_spec_count {checklist.slide_spec_count} < min_slides {min_slides}"
    )
    pptx = checklist.outputs_dir / "presentation.pptx"
    assert pptx.is_file() and pptx.stat().st_size > 1000, f"{project_id} PPTX too small or missing"
    manifest = json.loads((checklist.outputs_dir / "render_manifest.json").read_text(encoding="utf-8"))
    assert int(manifest.get("slide_count", 0)) == checklist.slide_spec_count
    visual = json.loads((checklist.outputs_dir / "visual_review.json").read_text(encoding="utf-8"))
    editability = json.loads(
        (checklist.outputs_dir / "editability_review.json").read_text(encoding="utf-8")
    )
    assert visual.get("source") == "placeholder"
    assert visual.get("review_completed") is False
    assert editability.get("source") == "placeholder"
    assert editability.get("passed") is False
    outline = json.loads((checklist.outputs_dir / "outline_plan.json").read_text(encoding="utf-8"))
    sections = outline.get("sections") or outline.get("chapters") or []
    assert sections, f"{project_id} outline_plan.json has no sections"
    return checklist
