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


class ElementComment(TimestampedModel):
    """Natural-language note bound to a RenderScene node.

    Binding ``node_id`` removes the need for the planner to guess the target
    from phrases like "右边第二张图". Status advances with SceneChangeProposal
    decisions while preserving Command / Patch / Proposal / QA / Revision.

    Version fields (``scene_revision_id`` / ``scene_hash`` / ``node_snapshot_json``)
    pin the comment to the formal scene at create time. Proposing against a
    newer revision must go through ``needs_rebase`` instead of silent apply.
    """

    id: UUID = Field(default_factory=new_uuid)
    presentation_id: UUID
    slide_id: UUID
    node_id: str = Field(min_length=1)
    layout_element_id: str | None = None

    note: str = Field(min_length=1)
    status: ElementCommentStatus = ElementCommentStatus.PENDING

    # Formal scene version at comment creation (audit / rebase gate).
    scene_revision_id: UUID | None = None
    scene_hash: str = ""
    node_snapshot_json: dict[str, Any] = Field(default_factory=dict)

    proposal_id: UUID | None = None
    created_by: str = "user"
