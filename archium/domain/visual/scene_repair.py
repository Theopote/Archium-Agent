"""RenderScene repair results — deterministic patches from semantic QA findings."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.render_scene import RenderScene


class SceneRepairAction(DomainModel):
    """One deterministic patch applied to a scene node."""

    scene_id: UUID
    node_id: str
    check_code: str
    action_type: str
    reason: str = ""


class SceneRepairResult(DomainModel):
    """Output of repairing a single RenderScene."""

    scene: RenderScene
    actions: list[SceneRepairAction] = Field(default_factory=list)
    applied_count: int = Field(default=0, ge=0)


class SceneRepairBatchResult(DomainModel):
    """Multi-round repair across a deck of scenes."""

    scenes: list[RenderScene] = Field(default_factory=list)
    actions: list[SceneRepairAction] = Field(default_factory=list)
    rounds: int = Field(default=0, ge=0)
    remaining_issue_count: int = Field(default=0, ge=0)
