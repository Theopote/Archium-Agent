"""Main-chain adoption — radar adopt concepts mapped to product-flow stages."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from archium.domain._base import DomainModel

MainChainStage = Literal["materials", "outline", "generate", "edit", "deliver"]


class AdoptLandingStatus(StrEnum):
    """Whether an adopt concept is landed for a project."""

    LANDED = "landed"
    PARTIAL = "partial"
    GAP = "gap"
    PLATFORM = "platform"


STAGE_LABELS_ZH: dict[str, str] = {
    "materials": "资料",
    "outline": "大纲",
    "generate": "生成",
    "edit": "工作室",
    "deliver": "交付",
}


class MainChainAdoptBinding(DomainModel):
    """Static mapping: radar adopt concept → main-chain enforcement point."""

    concept_id: str = Field(min_length=1, max_length=80)
    label_zh: str = Field(min_length=1, max_length=200)
    source_system_id: str = Field(min_length=1, max_length=80)
    main_chain_stage: MainChainStage
    enforcement_module: str = ""
    gate_hint_zh: str = ""
    platform_builtin: bool = False


class MainChainAdoptCheckpoint(DomainModel):
    """Per-project evaluation of one adopt binding."""

    binding: MainChainAdoptBinding
    status: AdoptLandingStatus = AdoptLandingStatus.GAP
    detail_zh: str = ""
    blocks_stage_advance: bool = False


class MainChainAdoptReport(DomainModel):
    """Deck-level adopt landing report for the main chain."""

    project_id: str
    presentation_id: str | None = None
    checkpoints: list[MainChainAdoptCheckpoint] = Field(default_factory=list)

    def for_stage(self, stage: MainChainStage) -> list[MainChainAdoptCheckpoint]:
        return [item for item in self.checkpoints if item.binding.main_chain_stage == stage]

    def landed_count(self) -> int:
        return sum(
            1
            for item in self.checkpoints
            if item.status in {AdoptLandingStatus.LANDED, AdoptLandingStatus.PLATFORM}
        )

    def gap_count(self) -> int:
        return sum(1 for item in self.checkpoints if item.status == AdoptLandingStatus.GAP)

    def stage_blockers(self, stage: MainChainStage) -> list[str]:
        return [
            f"{item.binding.label_zh}：{item.detail_zh}"
            for item in self.for_stage(stage)
            if item.blocks_stage_advance and item.status != AdoptLandingStatus.LANDED
        ]

    def stage_warnings(self, stage: MainChainStage) -> list[str]:
        return [
            f"{item.binding.label_zh}：{item.detail_zh}"
            for item in self.for_stage(stage)
            if item.status == AdoptLandingStatus.PARTIAL
        ]
