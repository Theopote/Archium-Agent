"""RenderScene repair results — deterministic patches from semantic QA findings."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.scene_qa import SceneSemanticCheckCode


class SceneRepairApplyMode(StrEnum):
    """How scene repair may be applied in a given workflow."""

    SAFE_AUTO_ONLY = "safe_auto_only"
    """Apply only lossless, non-semantic fixes (e.g. cover→contain)."""

    ALL_REPAIRABLE = "all_repairable"
    """Apply all bounded repair actions — requires Proposal review when used in Studio."""


class SceneRepairActionType(StrEnum):
    SET_FIT_MODE_CONTAIN = "set_fit_mode_contain"
    BUMP_FONT_SIZE = "bump_font_size"
    SHORTEN_TEXT = "shorten_text"
    SET_OVERFLOW_SHRINK = "set_overflow_shrink"


SAFE_AUTO_ACTION_TYPES = frozenset({SceneRepairActionType.SET_FIT_MODE_CONTAIN.value})

PROPOSAL_REQUIRED_REPAIR_CODES = frozenset(
    {
        SceneSemanticCheckCode.TEXT_OVERFLOW,
        SceneSemanticCheckCode.FONT_TOO_SMALL,
    }
)


def is_safe_auto_repair(action_type: str) -> bool:
    return action_type in SAFE_AUTO_ACTION_TYPES


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
    deferred_findings: list[SlideSemanticFinding] = Field(default_factory=list)
