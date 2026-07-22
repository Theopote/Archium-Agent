"""Studio AI edit command protocol — structured mutations on RenderScene."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel, new_uuid
from archium.domain.visual.render_scene import DrawingType, RenderScene

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


NodeAlignment = Literal[
    "left",
    "center",
    "right",
    "top",
    "middle",
    "bottom",
    "distribute_h",
    "distribute_v",
]

NodeReorderDirection = Literal["front", "back", "forward", "backward"]


class MoveNodeCommand(StudioCommandBase):
    """Move a render node to absolute page coordinates."""

    command_type: Literal["move_node"] = "move_node"
    node_id: str = Field(min_length=1)
    x: float
    y: float


class ResizeNodeCommand(StudioCommandBase):
    """Resize a render node to absolute page bounds."""

    command_type: Literal["resize_node"] = "resize_node"
    node_id: str = Field(min_length=1)
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    preserve_aspect_ratio: bool = False


class DeleteNodeCommand(StudioCommandBase):
    """Hide a render node from the scene (reversible via patch replay)."""

    command_type: Literal["delete_node"] = "delete_node"
    node_id: str = Field(min_length=1)


class SetNodeLockCommand(StudioCommandBase):
    """Lock/unlock a render node and optionally set lock scopes."""

    command_type: Literal["set_node_lock"] = "set_node_lock"
    node_id: str = Field(min_length=1)
    locked: bool = True
    lock_scopes: list[str] = Field(default_factory=list)


class SetNodeVisibilityCommand(StudioCommandBase):
    """Show or hide a render node without removing it from the scene."""

    command_type: Literal["set_node_visibility"] = "set_node_visibility"
    node_id: str = Field(min_length=1)
    visible: bool = True


class AlignNodesCommand(StudioCommandBase):
    """Align or distribute multiple render nodes."""

    command_type: Literal["align_nodes"] = "align_nodes"
    node_ids: list[str] = Field(min_length=1)
    alignment: NodeAlignment
    reference_node_id: str | None = None


class ReorderNodeCommand(StudioCommandBase):
    """Change render order (z-index) for one node."""

    command_type: Literal["reorder_node"] = "reorder_node"
    node_id: str = Field(min_length=1)
    direction: NodeReorderDirection


class UpdateNodeStyleCommand(StudioCommandBase):
    """Update visual style fields on a Text/Shape node (color, font size, fill)."""

    command_type: Literal["update_node_style"] = "update_node_style"
    node_id: str = Field(min_length=1)
    color: str | None = None
    font_size: float | None = Field(default=None, gt=0)
    fill_color: str | None = None


StudioCommand = Annotated[
    RewriteTextCommand
    | FixOverflowCommand
    | ReplaceAssetCommand
    | ReplaceDrawingCommand
    | IncreaseDrawingReadabilityCommand
    | MoveNodeCommand
    | ResizeNodeCommand
    | DeleteNodeCommand
    | SetNodeLockCommand
    | SetNodeVisibilityCommand
    | AlignNodesCommand
    | ReorderNodeCommand
    | UpdateNodeStyleCommand,
    Field(discriminator="command_type"),
]


class ScenePatchAction(DomainModel):
    """One reversible patch applied to a RenderScene node."""

    action_id: UUID = Field(default_factory=new_uuid)
    command_id: UUID | None = None
    scene_id: UUID
    slide_id: UUID
    base_scene_hash: str = Field(min_length=1)
    node_id: str
    action_type: str = Field(min_length=1)
    property_name: str = ""
    before_value: str | None = None
    after_value: str | None = None
    after_asset_id: UUID | None = None
    before_payload: dict[str, Any] = Field(default_factory=dict)
    after_payload: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


def build_patch_action(
    scene: RenderScene,
    *,
    base_scene_hash: str,
    **fields: object,
) -> ScenePatchAction:
    """Create a patch action bound to a concrete RenderScene identity."""
    return ScenePatchAction(
        scene_id=scene.id,
        slide_id=scene.slide_id,
        base_scene_hash=base_scene_hash,
        **fields,  # type: ignore[arg-type]
    )
