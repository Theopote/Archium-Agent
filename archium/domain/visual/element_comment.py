"""Element-bound natural-language comments for Studio scene edits."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import TimestampedModel, new_uuid


class ElementCommentStatus(StrEnum):
    """Lifecycle of an element-bound Studio comment."""

    PENDING = "pending"
    PROPOSED = "proposed"
    NEEDS_REBASE = "needs_rebase"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RESOLVED = "resolved"


ElementCommentStatusLiteral = Literal[
    "pending",
    "proposed",
    "needs_rebase",
    "accepted",
    "rejected",
    "resolved",
]


class ElementCommentScope(StrEnum):
    """How widely a comment may mutate nodes.

    Default ``NODE`` keeps the hard-bound single-target contract. Wider scopes
    must be chosen explicitly by the user or Planner before multi-node edits
    (equalize sizes, reflow columns, etc.) are allowed.
    """

    NODE = "node"
    NODE_AND_REFERENCES = "node_and_references"
    SELECTION = "selection"
    REGION = "region"
    SLIDE = "slide"


ElementCommentScopeLiteral = Literal[
    "node",
    "node_and_references",
    "selection",
    "region",
    "slide",
]


class ElementComment(TimestampedModel):
    """Natural-language note bound to a RenderScene node.

    Binding ``node_id`` removes the need for the planner to guess the target
    from phrases like "右边第二张图". Status advances with SceneChangeProposal
    decisions while preserving Command / Patch / Proposal / QA / Revision.

    Version fields (``scene_revision_id`` / ``scene_hash`` / ``node_snapshot_json``)
    pin the comment to the formal scene at create time. Proposing against a
    newer revision must go through ``needs_rebase`` instead of silent apply.

    ``scope`` defaults to ``NODE`` (hard bind). Expand to
    ``NODE_AND_REFERENCES`` / ``SELECTION`` / ``REGION`` / ``SLIDE`` when the
    note intentionally covers more than the primary node.
    """

    id: UUID = Field(default_factory=new_uuid)
    presentation_id: UUID
    slide_id: UUID
    node_id: str = Field(min_length=1)
    layout_element_id: str | None = None

    note: str = Field(min_length=1)
    status: ElementCommentStatus = ElementCommentStatus.PENDING
    scope: ElementCommentScope = ElementCommentScope.NODE
    # Extra nodes for SELECTION / NODE_AND_REFERENCES / pre-resolved REGION.
    scope_node_ids: list[str] = Field(default_factory=list)
    # Optional axis-aligned region in page inches: x, y, width, height.
    region_bbox: dict[str, float] | None = None

    # Formal scene version at comment creation (audit / rebase gate).
    scene_revision_id: UUID | None = None
    scene_hash: str = ""
    node_snapshot_json: dict[str, Any] = Field(default_factory=dict)

    proposal_id: UUID | None = None
    created_by: str = "user"

    def allowed_node_ids(self, *, scene_node_ids: set[str] | None = None) -> set[str] | None:
        """Return the allowed mutation set, or ``None`` when unrestricted (SLIDE)."""
        if self.scope == ElementCommentScope.SLIDE:
            return None
        allowed = {self.node_id, *self.scope_node_ids}
        if self.scope == ElementCommentScope.NODE:
            return {self.node_id}
        if self.scope == ElementCommentScope.REGION and self.region_bbox and scene_node_ids is not None:
            # Caller may pass ids already filtered to the region; merge both.
            allowed |= set(scene_node_ids)
        return allowed
