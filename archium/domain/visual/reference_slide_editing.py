"""Reference slide edit-action models (Phase 6 skeleton)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.render_scene import RenderScene


class ReferenceEditActionKind(StrEnum):
    REPLACE_TEXT = "replace_text"
    REPLACE_ASSET = "replace_asset"
    REMOVE_REFERENCE_ASSET = "remove_reference_asset"
    PRESERVE_DECORATION = "preserve_decoration"
    SKIP_UNSUPPORTED = "skip_unsupported"


class BaseReferenceEditAction(DomainModel):
    action_type: str
    element_id: str
    reason: str = ""


class ReplaceTextAction(BaseReferenceEditAction):
    action_type: Literal["replace_text"] = "replace_text"
    semantic_role: str = ""
    reference_text: str = ""
    replacement_text: str = ""


class ReplaceAssetAction(BaseReferenceEditAction):
    action_type: Literal["replace_asset"] = "replace_asset"
    visual_role: str = ""
    asset_id: UUID | None = None
    storage_uri: str = ""


class RemoveReferenceAssetAction(BaseReferenceEditAction):
    action_type: Literal["remove_reference_asset"] = "remove_reference_asset"
    reference_asset_id: str = ""
    reference_relative_path: str = ""


class PreserveDecorationAction(BaseReferenceEditAction):
    action_type: Literal["preserve_decoration"] = "preserve_decoration"
    shape_kind: str = "rectangle"
    locked: bool = True


class SkipUnsupportedAction(BaseReferenceEditAction):
    action_type: Literal["skip_unsupported"] = "skip_unsupported"
    element_type: str = ""
    warning: str = ""


ReferenceEditAction = Annotated[
    ReplaceTextAction
    | ReplaceAssetAction
    | RemoveReferenceAssetAction
    | PreserveDecorationAction
    | SkipUnsupportedAction,
    Field(discriminator="action_type"),
]


class ReferenceSlideEditResult(DomainModel):
    """Output of reference-structure copy + content strip + project fill."""

    scene: RenderScene
    actions: list[ReferenceEditAction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reference_content_stripped: bool = True
    stripped_text_count: int = Field(default=0, ge=0)
    stripped_asset_count: int = Field(default=0, ge=0)
