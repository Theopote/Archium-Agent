"""Runtime enforcement for artifact ownership and reconciliation boundaries."""

from __future__ import annotations

from enum import StrEnum
from typing import cast
from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel
from archium.domain.artifact_ownership import (
    ArtifactAuthority,
    ArtifactKind,
    ArtifactOwnershipContract,
    ownership_for,
)
from archium.exceptions import WorkflowError


class ArtifactMutationOperation(StrEnum):
    CREATE = "create"
    DERIVE = "derive"
    IMPORT_EXTERNAL = "import_external"
    OVERWRITE_CANONICAL = "overwrite_canonical"
    RECONCILE_ACCEPTED = "reconcile_accepted"


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
        return contract

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
