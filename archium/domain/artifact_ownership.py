"""Ownership and regeneration rules for presentation pipeline artifacts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class ArtifactKind(StrEnum):
    PROJECT_KNOWLEDGE = "project_knowledge"
    OUTLINE_PLAN = "outline_plan"
    SLIDE_DESIGN_BRIEF = "slide_design_brief"
    LAYOUT_PLAN = "layout_plan"
    RENDER_SCENE = "render_scene"
    PREVIEW_PNG = "preview_png"
    PPTX = "pptx"
    ROUND_TRIP_PNG = "round_trip_png"
    EXPORT_MANIFEST = "export_manifest"


class ArtifactAuthority(StrEnum):
    SOURCE = "source"
    AUTHORED_STATE = "authored_state"
    DERIVED_ARTIFACT = "derived_artifact"
    DELIVERY_ARTIFACT = "delivery_artifact"
    VALIDATION_ARTIFACT = "validation_artifact"


class ArtifactOwnershipContract(DomainModel):
    kind: ArtifactKind
    authority: ArtifactAuthority
    owner: str = Field(min_length=1)
    user_editable: bool
    reproducible: bool
    reconcile_required: bool = False
    derived_from: tuple[ArtifactKind, ...] = Field(default_factory=tuple)


ARTIFACT_OWNERSHIP: dict[ArtifactKind, ArtifactOwnershipContract] = {
    ArtifactKind.PROJECT_KNOWLEDGE: ArtifactOwnershipContract(
        kind=ArtifactKind.PROJECT_KNOWLEDGE,
        authority=ArtifactAuthority.SOURCE,
        owner="main_chain",
        user_editable=True,
        reproducible=False,
    ),
    ArtifactKind.OUTLINE_PLAN: ArtifactOwnershipContract(
        kind=ArtifactKind.OUTLINE_PLAN,
        authority=ArtifactAuthority.AUTHORED_STATE,
        owner="user_and_main_chain",
        user_editable=True,
        reproducible=True,
        derived_from=(ArtifactKind.PROJECT_KNOWLEDGE,),
    ),
    ArtifactKind.SLIDE_DESIGN_BRIEF: ArtifactOwnershipContract(
        kind=ArtifactKind.SLIDE_DESIGN_BRIEF,
        authority=ArtifactAuthority.AUTHORED_STATE,
        owner="user_and_main_chain",
        user_editable=True,
        reproducible=True,
        derived_from=(ArtifactKind.OUTLINE_PLAN,),
    ),
    ArtifactKind.LAYOUT_PLAN: ArtifactOwnershipContract(
        kind=ArtifactKind.LAYOUT_PLAN,
        authority=ArtifactAuthority.AUTHORED_STATE,
        owner="visual_planner",
        user_editable=True,
        reproducible=True,
        derived_from=(ArtifactKind.SLIDE_DESIGN_BRIEF,),
    ),
    ArtifactKind.RENDER_SCENE: ArtifactOwnershipContract(
        kind=ArtifactKind.RENDER_SCENE,
        authority=ArtifactAuthority.AUTHORED_STATE,
        owner="studio",
        user_editable=True,
        reproducible=True,
        derived_from=(ArtifactKind.LAYOUT_PLAN,),
    ),
    ArtifactKind.PREVIEW_PNG: ArtifactOwnershipContract(
        kind=ArtifactKind.PREVIEW_PNG,
        authority=ArtifactAuthority.DERIVED_ARTIFACT,
        owner="renderer",
        user_editable=False,
        reproducible=True,
        derived_from=(ArtifactKind.RENDER_SCENE,),
    ),
    ArtifactKind.PPTX: ArtifactOwnershipContract(
        kind=ArtifactKind.PPTX,
        authority=ArtifactAuthority.DELIVERY_ARTIFACT,
        owner="delivery",
        user_editable=True,
        reproducible=True,
        reconcile_required=True,
        derived_from=(ArtifactKind.RENDER_SCENE,),
    ),
    ArtifactKind.ROUND_TRIP_PNG: ArtifactOwnershipContract(
        kind=ArtifactKind.ROUND_TRIP_PNG,
        authority=ArtifactAuthority.VALIDATION_ARTIFACT,
        owner="qa",
        user_editable=False,
        reproducible=True,
        derived_from=(ArtifactKind.PPTX,),
    ),
    ArtifactKind.EXPORT_MANIFEST: ArtifactOwnershipContract(
        kind=ArtifactKind.EXPORT_MANIFEST,
        authority=ArtifactAuthority.VALIDATION_ARTIFACT,
        owner="delivery",
        user_editable=False,
        reproducible=True,
        derived_from=(ArtifactKind.PPTX,),
    ),
}


def ownership_for(kind: ArtifactKind) -> ArtifactOwnershipContract:
    return ARTIFACT_OWNERSHIP[kind]


def can_overwrite_canonical_state(kind: ArtifactKind) -> bool:
    """External edits never silently flow back from derived/delivery artifacts."""
    return ARTIFACT_OWNERSHIP[kind].authority in {
        ArtifactAuthority.SOURCE,
        ArtifactAuthority.AUTHORED_STATE,
    }

