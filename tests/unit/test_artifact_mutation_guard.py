from uuid import uuid4

import pytest
from archium.application.artifact_policy_service import (
    ArtifactMutationGuard,
    ArtifactMutationOperation,
    ReconciliationProposalStatus,
)
from archium.domain.artifact_ownership import ArtifactKind, ArtifactRecord
from archium.exceptions import WorkflowError


def test_pptx_cannot_directly_overwrite_render_scene() -> None:
    guard = ArtifactMutationGuard()
    with pytest.raises(WorkflowError, match="Invalid artifact derivation"):
        guard.validate_derivation(ArtifactKind.PPTX, ArtifactKind.RENDER_SCENE)
    with pytest.raises(WorkflowError, match="reconciliation proposal"):
        guard.require_writable(ArtifactKind.PPTX, ArtifactMutationOperation.IMPORT_EXTERNAL)


def test_pptx_reconciliation_requires_proposal_diff_and_user_acceptance() -> None:
    guard = ArtifactMutationGuard()
    proposal = guard.propose_reconciliation(
        project_id=uuid4(),
        presentation_id=uuid4(),
        source_artifact_id=uuid4(),
        source_kind=ArtifactKind.PPTX,
        target_kind=ArtifactKind.RENDER_SCENE,
        base_revision_id=uuid4(),
        diff={"changed_nodes": ["title"]},
    )
    assert proposal.status == ReconciliationProposalStatus.PROPOSED
    accepted = guard.accept_reconciliation(proposal)
    assert accepted.status == ReconciliationProposalStatus.ACCEPTED


def test_declared_render_scene_to_pptx_derivation_is_allowed() -> None:
    target = ArtifactMutationGuard().validate_derivation(
        ArtifactKind.RENDER_SCENE, ArtifactKind.PPTX
    )
    assert target.kind == ArtifactKind.PPTX


def test_artifact_record_binds_revision_hash_and_generator_lineage() -> None:
    source_id = uuid4()
    record = ArtifactRecord(
        kind=ArtifactKind.PPTX,
        project_id=uuid4(),
        presentation_id=uuid4(),
        revision_id=uuid4(),
        content_hash="a" * 64,
        derived_from_artifact_ids=(source_id,),
        generator_version="pptxgenjs-3.12/archium-v1",
        font_manifest_hash="b" * 64,
        theme_version="theme-v7",
        export_policy="editable-balanced-v1",
    )
    assert record.derived_from_artifact_ids == (source_id,)
