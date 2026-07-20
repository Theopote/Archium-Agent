"""Phase 7 real-project folder scaffold tests."""

from __future__ import annotations

import pytest
from archium.domain.project_acceptance import RealProjectScenario

from tests.e2e.real_projects.loader import load_manifest
from tests.e2e.real_projects.phase7_loader import (
    list_phase7_project_ids,
    load_phase7_project,
    required_phase7_paths,
    resolve_input_manifest_path,
)


@pytest.mark.parametrize("project_id", list_phase7_project_ids())
def test_phase7_project_has_required_artifacts(project_id: str) -> None:
    for path in required_phase7_paths(project_id):
        assert path.exists(), f"missing {path}"


@pytest.mark.parametrize("project_id", list_phase7_project_ids())
def test_phase7_profile_matches_folder(project_id: str) -> None:
    bundle = load_phase7_project(project_id)
    assert bundle.profile.id == project_id
    assert bundle.human_review is not None
    assert bundle.human_review.source == "manual"
    assert bundle.acceptance_record is not None
    assert bundle.acceptance_record["human_rehearsal_passed"] is False


def test_cultural_village_manifest_is_loadable() -> None:
    bundle = load_phase7_project("cultural_village_001")
    assert bundle.profile.scenario == RealProjectScenario.CULTURAL_VILLAGE
    manifest_path = resolve_input_manifest_path(bundle)
    loaded = load_manifest(manifest_path)
    assert loaded.manifest.scenario == RealProjectScenario.CULTURAL_VILLAGE
    assert loaded.manifest.expectations.get("requires_cultural_narrative") is True


def test_renovation_manifest_uses_phase7_drop_in_files() -> None:
    bundle = load_phase7_project("renovation_001")
    assert bundle.profile.scenario == RealProjectScenario.EXISTING_RENOVATION
    manifest_path = resolve_input_manifest_path(bundle)
    loaded = load_manifest(manifest_path)
    assert loaded.manifest.project_id == "renovation_001"
    assert len(loaded.raw.get("files", [])) >= 16
