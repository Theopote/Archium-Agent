"""Studio AI edit command protocol — structured mutations on RenderScene."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel, new_uuid
from archium.domain.visual.render_scene import DrawingType

ImageAssetOrigin = Literal[
    "project_upload",
    "public_research",
    "reference_case",
    "ai_generated",
    "stock_image",
]


class StudioCommandBase(DomainModel):
    """Shared envelope for all Studio edit commands."""

    command_id: UUID = Field(default_factory=new_uuid)
    command_type: str
    presentation_id: UUID
    slide_id: UUID
    target_node_ids: list[str] = Field(default_factory=list)
    requested_by: Literal["user", "critic", "workflow"] = "user"
    reason: str = ""
    expected_effect: str = ""


class RewriteTextCommand(StudioCommandBase):
    """Replace text content on a single TextNode."""

    command_type: Literal["rewrite_text"] = "rewrite_text"
    node_id: str = Field(min_length=1)
    new_text: str


class FixOverflowCommand(StudioCommandBase):
    """Repair text overflow on one or more TextNodes."""

    command_type: Literal["fix_overflow"] = "fix_overflow"
    node_ids: list[str] | None = None
    allow_shorten: bool = True
    allow_shrink_policy: bool = True


class ReplaceAssetCommand(StudioCommandBase):
    """Replace the bound asset on an ImageNode."""

    command_type: Literal["replace_asset"] = "replace_asset"
    node_id: str = Field(min_length=1)
    asset_id: UUID
    storage_uri: str = Field(min_length=1)
    asset_origin: ImageAssetOrigin = "project_upload"


class ReplaceDrawingCommand(StudioCommandBase):
    """Replace the bound asset on a DrawingNode (always contain fit)."""

    command_type: Literal["replace_drawing"] = "replace_drawing"
    node_id: str = Field(min_length=1)
    asset_id: UUID
    storage_uri: str = Field(min_length=1)
    drawing_type: DrawingType | None = None
    preserve_aspect_ratio: bool = True
    preserve_annotations: bool = True


class IncreaseDrawingReadabilityCommand(StudioCommandBase):
    """Enlarge a drawing node and compress supporting body content."""

    command_type: Literal["increase_drawing_readability"] = "increase_drawing_readability"
    node_id: str = Field(min_length=1)
    target_min_area_ratio: float = Field(default=0.45, gt=0, le=1.0)
    allow_reduce_body_text: bool = True
    preserve_aspect_ratio: bool = True
    preserve_annotations: bool = True
    forbid_cover_crop: bool = True


StudioCommand = Annotated[
    RewriteTextCommand
    | FixOverflowCommand
    | ReplaceAssetCommand
    | ReplaceDrawingCommand
    | IncreaseDrawingReadabilityCommand,
    Field(discriminator="command_type"),
]


class ScenePatchAction(DomainModel):
    """One reversible patch applied to a RenderScene node."""

    action_id: UUID = Field(default_factory=new_uuid)
    command_id: UUID | None = None
    scene_id: UUID
    node_id: str
    action_type: str = Field(min_length=1)
    property_name: str = ""
    before_value: str | None = None
    after_value: str | None = None
    after_asset_id: UUID | None = None
    before_payload: dict[str, Any] = Field(default_factory=dict)
    after_payload: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
