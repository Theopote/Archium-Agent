"""Runtime enforcement for artifact ownership and reconciliation boundaries."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel
from archium.domain.artifact_ownership import (
    ArtifactAuthority,
    ArtifactKind,
    ArtifactOwnershipContract,
    ownership_for,
)
from archium.domain.visual.render_scene import RenderScene
from archium.exceptions import WorkflowError


class ArtifactMutationOperation(StrEnum):
    CREATE = "create"
    DERIVE = "derive"
    IMPORT_EXTERNAL = "import_external"
    OVERWRITE_CANONICAL = "overwrite_canonical"
    RECONCILE_ACCEPTED = "reconcile_accepted"
    INGEST_REFERENCE = "ingest_reference"


class ReconciliationProposalStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ArtifactReconciliationProposal(IdentifiedModel):
    project_id: UUID
    presentation_id: UUID
    source_artifact_id: UUID
    source_kind: ArtifactKind
    target_kind: ArtifactKind
    base_revision_id: UUID
    diff: dict[str, object] = Field(default_factory=dict)
    status: ReconciliationProposalStatus = ReconciliationProposalStatus.PROPOSED


class ArtifactMutationGuard:
    """Fail-closed policy applied before artifact-writing side effects."""

    def require_writable(
        self,
        kind: ArtifactKind,
        operation: ArtifactMutationOperation,
    ) -> ArtifactOwnershipContract:
        contract = ownership_for(kind)
        if operation == ArtifactMutationOperation.OVERWRITE_CANONICAL and contract.authority not in {
            ArtifactAuthority.SOURCE,
            ArtifactAuthority.AUTHORED_STATE,
        }:
            raise WorkflowError(f"{kind.value} cannot overwrite canonical authored state")
        if operation == ArtifactMutationOperation.IMPORT_EXTERNAL and contract.reconcile_required:
            raise WorkflowError(
                f"External {kind.value} requires a reconciliation proposal before scene mutation"
            )
        if operation == ArtifactMutationOperation.RECONCILE_ACCEPTED and not contract.reconcile_required:
            raise WorkflowError(f"{kind.value} has no reconciliation contract")
        if (
            operation == ArtifactMutationOperation.INGEST_REFERENCE
            and kind not in {ArtifactKind.PPTX, ArtifactKind.PROJECT_KNOWLEDGE}
        ):
            raise WorkflowError(f"{kind.value} cannot be ingested as a reference artifact")
        return contract

    def require_entry(
        self,
        kind: ArtifactKind,
        operation: ArtifactMutationOperation,
        *,
        entrypoint: str,
    ) -> ArtifactOwnershipContract:
        """Named write-entry gate used by Import / Recovery / Restore / Fill / Reconcile."""
        require_artifact_write_entrypoint(entrypoint)
        try:
            return self.require_writable(kind, operation)
        except WorkflowError as exc:
            raise WorkflowError(f"{entrypoint}: {exc}") from exc

    def require_reconcile(self, kind: ArtifactKind) -> ArtifactOwnershipContract:
        contract = ownership_for(kind)
        if not contract.reconcile_required:
            raise WorkflowError(f"{kind.value} does not support reconciliation")
        return contract

    def validate_derivation(
        self,
        source_kind: ArtifactKind,
        target_kind: ArtifactKind,
    ) -> ArtifactOwnershipContract:
        target = ownership_for(target_kind)
        if source_kind not in target.derived_from:
            raise WorkflowError(
                f"Invalid artifact derivation: {source_kind.value} -> {target_kind.value}"
            )
        return target

    def propose_reconciliation(
        self,
        *,
        project_id: UUID,
        presentation_id: UUID,
        source_artifact_id: UUID,
        source_kind: ArtifactKind,
        target_kind: ArtifactKind,
        base_revision_id: UUID,
        diff: dict[str, object],
    ) -> ArtifactReconciliationProposal:
        self.require_reconcile(source_kind)
        self.validate_derivation(source_kind, ArtifactKind.RECONCILIATION_PROPOSAL)
        if target_kind != ArtifactKind.RENDER_SCENE:
            raise WorkflowError("V1 reconciliation target must be render_scene")
        return ArtifactReconciliationProposal(
            project_id=project_id,
            presentation_id=presentation_id,
            source_artifact_id=source_artifact_id,
            source_kind=source_kind,
            target_kind=target_kind,
            base_revision_id=base_revision_id,
            diff=diff,
        )

    def accept_reconciliation(
        self, proposal: ArtifactReconciliationProposal
    ) -> ArtifactReconciliationProposal:
        if proposal.status != ReconciliationProposalStatus.PROPOSED:
            raise WorkflowError("Only a proposed reconciliation can be accepted")
        self.require_writable(
            proposal.source_kind,
            ArtifactMutationOperation.RECONCILE_ACCEPTED,
        )
        return cast(
            ArtifactReconciliationProposal,
            proposal.model_copy(update={"status": ReconciliationProposalStatus.ACCEPTED}),
        )


class RenderSceneWriter(Protocol):
    def save(self, scene: RenderScene) -> RenderScene: ...


def save_render_scene(
    writer: RenderSceneWriter,
    scene: RenderScene,
    *,
    operation: ArtifactMutationOperation = ArtifactMutationOperation.CREATE,
    entrypoint: str = "save_render_scene",
) -> RenderScene:
    """The single policy-enforced gateway for canonical RenderScene writes."""
    ArtifactMutationGuard().require_entry(
        ArtifactKind.RENDER_SCENE,
        operation,
        entrypoint=entrypoint,
    )
    return writer.save(scene)


def save_reconciled_render_scene(
    writer: RenderSceneWriter,
    scene: RenderScene,
    proposal: ArtifactReconciliationProposal,
) -> tuple[RenderScene, ArtifactReconciliationProposal]:
    """Accept a PPTX→scene reconciliation proposal, then write RenderScene.

    Proposal acceptance gates PPTX ``RECONCILE_ACCEPTED``; the scene write uses
    ``OVERWRITE_CANONICAL`` because RenderScene is authored state (not
    reconcile_required itself).
    """
    accepted = ArtifactMutationGuard().accept_reconciliation(proposal)
    saved = save_render_scene(
        writer,
        scene,
        operation=ArtifactMutationOperation.OVERWRITE_CANONICAL,
        entrypoint="pptx.reconcile.accept",
    )
    return saved, accepted


# Named write entrypoints that must go through ArtifactMutationGuard.
ARTIFACT_WRITE_ENTRYPOINTS: frozenset[str] = frozenset(
    {
        "template_studio.import_pptx",
        "slide_recovery.import_external_scene",
        "scene_revision.restore",
        "reference_slide_editing.generate_scene",
        "pptx.reconcile.accept",
        "save_render_scene",
        "delivery.record_pptx_export",
    }
)


def require_artifact_write_entrypoint(entrypoint: str) -> str:
    """Fail closed when a write path uses an unregistered ownership entrypoint."""
    key = entrypoint.strip()
    if key not in ARTIFACT_WRITE_ENTRYPOINTS:
        raise WorkflowError(
            f"Unregistered artifact write entrypoint: {entrypoint!r}. "
            f"Register it in ARTIFACT_WRITE_ENTRYPOINTS."
        )
    return key


def reconcile_pptx_into_scene(
    writer: RenderSceneWriter,
    scene: RenderScene,
    *,
    project_id: UUID,
    presentation_id: UUID,
    source_artifact_id: UUID,
    base_revision_id: UUID,
    diff: dict[str, object] | None = None,
) -> tuple[RenderScene, ArtifactReconciliationProposal]:
    """Product path: propose → accept → save reconciled RenderScene from PPTX import."""
    guard = ArtifactMutationGuard()
    proposal = guard.propose_reconciliation(
        project_id=project_id,
        presentation_id=presentation_id,
        source_artifact_id=source_artifact_id,
        source_kind=ArtifactKind.PPTX,
        target_kind=ArtifactKind.RENDER_SCENE,
        base_revision_id=base_revision_id,
        diff=diff or {},
    )
    return save_reconciled_render_scene(writer, scene, proposal)

