"""Load Phase 7 real-project acceptance folder scaffolds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archium.domain.project_acceptance import Phase7HumanReviewBundle, Phase7ProjectProfile

_PHASE7_ROOT = Path(__file__).resolve().parent
PHASE7_PROJECT_IDS = ("cultural_village_001", "renovation_001")


@dataclass(frozen=True)
class Phase7ProjectBundle:
    """All on-disk artifacts for one Phase 7 acceptance project."""

    project_id: str
    root: Path
    profile: Phase7ProjectProfile
    input_manifest: dict[str, Any]
    acceptance_record: dict[str, Any] | None
    human_review: Phase7HumanReviewBundle | None


def phase7_project_root(project_id: str) -> Path:
    return _PHASE7_ROOT / project_id


def list_phase7_project_ids() -> list[str]:
    return [
        project_id
        for project_id in PHASE7_PROJECT_IDS
        if phase7_project_root(project_id).is_dir()
    ]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_phase7_project(project_id: str) -> Phase7ProjectBundle:
    root = phase7_project_root(project_id)
    if not root.is_dir():
        msg = f"Phase 7 project folder not found: {root}"
        raise FileNotFoundError(msg)

    profile = Phase7ProjectProfile.model_validate(
        _read_json(root / "project_profile.json")
    )
    input_manifest = _read_json(root / "input_manifest.json")

    acceptance_path = root / "acceptance_record.json"
    acceptance_record = _read_json(acceptance_path) if acceptance_path.exists() else None

    human_path = root / "human_review.json"
    human_review = None
    if human_path.exists():
        human_review = Phase7HumanReviewBundle.model_validate(_read_json(human_path))

    return Phase7ProjectBundle(
        project_id=project_id,
        root=root,
        profile=profile,
        input_manifest=input_manifest,
        acceptance_record=acceptance_record,
        human_review=human_review,
    )


def resolve_input_manifest_path(bundle: Phase7ProjectBundle) -> Path:
    """Return manifest JSON used to seed the automated pipeline."""
    manifest_ref = bundle.input_manifest.get("manifest_ref")
    if isinstance(manifest_ref, str) and manifest_ref.strip():
        return (bundle.root / manifest_ref).resolve()
    inline = bundle.input_manifest.get("inline_manifest")
    if isinstance(inline, dict):
        inline_path = bundle.root / "inline_manifest.resolved.json"
        inline_path.write_text(
            json.dumps(inline, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return inline_path
    msg = f"{bundle.project_id} input_manifest.json missing manifest_ref or inline_manifest"
    raise ValueError(msg)


def required_phase7_paths(project_id: str) -> list[Path]:
    root = phase7_project_root(project_id)
    return [
        root / "project_profile.json",
        root / "input_manifest.json",
        root / "research_report.json",
        root / "outline_plan.json",
        root / "acceptance_record.json",
        root / "human_review.json",
        root / "output",
        root / "output" / "slides",
    ]
