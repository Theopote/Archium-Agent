"""Timeline summaries for RenderScene revision history."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.scene_change_proposal import SceneRevisionSource

SceneRevisionTimelineSource = Literal[
    "manual_edit",
    "ai_proposal",
    "qa_repair",
    "layout_replan",
    "asset_rebind",
    "import_recovery",
]

_SCENE_SOURCE_TO_TIMELINE: dict[SceneRevisionSource, SceneRevisionTimelineSource] = {
    "manual": "manual_edit",
    "ai_proposal": "ai_proposal",
    "automatic_repair": "qa_repair",
    "template_application": "layout_replan",
    "import_recovery": "import_recovery",
}


def map_scene_revision_source(source: str) -> SceneRevisionTimelineSource:
    """Map persisted ``SceneRevisionSource`` values to timeline labels."""
    if source in _SCENE_SOURCE_TO_TIMELINE:
        return _SCENE_SOURCE_TO_TIMELINE[cast(SceneRevisionSource, source)]
    if source in {
        "manual_edit",
        "ai_proposal",
        "qa_repair",
        "layout_replan",
        "asset_rebind",
        "import_recovery",
    }:
        return source  # type: ignore[return-value]
    return "manual_edit"


class SceneRevisionSummary(DomainModel):
    """One row in the Studio visual version timeline."""

    revision_id: UUID
    scene_id: UUID
    version: int = Field(ge=0, description="Entity revision number; 0 for rejected proposals.")
    source: SceneRevisionTimelineSource
    summary: str
    command_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    qa_status: str = "unknown"
    accepted: bool = True
    is_current: bool = False
    parent_revision_id: UUID | None = None
    proposal_id: UUID | None = None


class SceneRevisionRestoreResult(DomainModel):
    """Outcome of restoring a historical RenderScene revision.

    Restore always creates a **new** revision based on the source snapshot;
    historical revisions remain intact.
    """

    summary: SceneRevisionSummary
    restored_scene_id: UUID
    source_revision_id: UUID
    source_version: int = Field(ge=0)
