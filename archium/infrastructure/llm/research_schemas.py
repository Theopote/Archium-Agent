"""Structured LLM output for autonomous research synthesis."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchSourceDraft(BaseModel):
    title: str = Field(min_length=1)
    url: str | None = None
    note: str = ""


class ResearchFindingDraft(BaseModel):
    topic: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    problem: str = Field(
        default="",
        description="Design problem / contradiction addressed.",
    )
    insight: str = Field(
        default="",
        description="Why this matters for design (not a case dump).",
    )
    strategy: str = Field(
        default="",
        description="Core architectural strategy (one line).",
    )
    principle: str = Field(
        default="",
        description="Transferable design principle.",
    )
    spatial_translation: str = Field(
        default="",
        description="Spatial organization implication.",
    )
    material_strategy: str = Field(
        default="",
        description="Material / tectonic implication when known.",
    )
    project_link: str = Field(
        default="",
        description="Link to current project; may mirror relevance.",
    )
    applicability: str = Field(
        default="",
        description="Applicability boundaries.",
    )
    precedent_ref: str | None = Field(
        default=None,
        description="Optional ArchitectureCase ref, e.g. case:ningbo_museum.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Short evidence labels beyond suggested_sources.",
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Legacy / supplemental bullets; prefer labeled 问题/策略/原则/空间/材料/关联/适用/先例.",
    )
    suggested_sources: list[ResearchSourceDraft] = Field(default_factory=list)
    relevance: str = ""


class AutonomousResearchDraft(BaseModel):
    findings: list[ResearchFindingDraft] = Field(default_factory=list)
