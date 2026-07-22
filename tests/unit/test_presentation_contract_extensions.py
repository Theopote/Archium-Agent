from uuid import uuid4

from archium.domain.architectural_narrative_mode import (
    ArchitecturalNarrativeMode,
    contract_for_narrative_mode,
)
from archium.domain.artifact_ownership import (
    ArtifactAuthority,
    ArtifactKind,
    can_overwrite_canonical_state,
    ownership_for,
)
from archium.domain.enums import NarrativeStage
from archium.domain.project_mission import ProjectMission


def test_narrative_mode_is_an_explicit_axis_with_a_stage_contract() -> None:
    contract = contract_for_narrative_mode(ArchitecturalNarrativeMode.DECISION_FIRST)
    assert contract.stage_sequence[0] == NarrativeStage.DECISION
    assert "approval" in contract.suitable_decision_contexts


def test_mission_can_lock_narrative_mode_independently() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="Option review",
        task_statement="Select a preferred architectural option",
        narrative_mode=ArchitecturalNarrativeMode.OPTION_COMPARISON,
    )
    assert mission.narrative_mode == ArchitecturalNarrativeMode.OPTION_COMPARISON


def test_render_scene_is_authored_state_and_pptx_is_delivery() -> None:
    scene = ownership_for(ArtifactKind.RENDER_SCENE)
    pptx = ownership_for(ArtifactKind.PPTX)
    assert scene.authority == ArtifactAuthority.AUTHORED_STATE
    assert pptx.authority == ArtifactAuthority.DELIVERY_ARTIFACT
    assert pptx.reconcile_required
    assert ArtifactKind.RENDER_SCENE in pptx.derived_from


def test_delivery_edits_cannot_silently_overwrite_canonical_state() -> None:
    assert can_overwrite_canonical_state(ArtifactKind.RENDER_SCENE)
    assert not can_overwrite_canonical_state(ArtifactKind.PPTX)
    assert not can_overwrite_canonical_state(ArtifactKind.PREVIEW_PNG)
