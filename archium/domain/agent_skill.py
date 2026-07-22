"""Archium product Agent Skill definitions and invocation audit."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from archium.domain._base import DomainModel, utc_now

SkillTaskType = Literal[
    "art_direction",
    "outline",
    "slide_plan",
    "layout_plan",
    "manuscript",
    "visual_qa",
    "studio_edit",
    "studio_comment",
    "element_edit_intent",
    "drawing_page",
    "photo_evidence",
    "executive_summary",
    "renovation_report",
]


class ArchiumSkillDefinition(DomainModel):
    """Product skill asset — selectable, prompt-injectable, auditable."""

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    applicable_stages: list[str] = Field(default_factory=list)
    applicable_slide_types: list[str] = Field(default_factory=list)
    applicable_project_types: list[str] = Field(default_factory=list)
    applicable_audiences: list[str] = Field(default_factory=list)
    required_rules: list[str] = Field(default_factory=list)
    prompt_uri: str = Field(min_length=1)
    checksum: str = Field(min_length=1)
    body: str = ""


class SkillInvocationAudit(DomainModel):
    """Record of skills applied to one model call / workflow step."""

    task_type: str = ""
    slide_type: str | None = None
    project_type: str | None = None
    audience: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    skill_versions: list[str] = Field(default_factory=list)
    skill_checksums: list[str] = Field(default_factory=list)
    prompt_uris: list[str] = Field(default_factory=list)
    selected_at: datetime = Field(default_factory=utc_now)

    def to_llm_metadata(self) -> dict[str, str]:
        """Flatten into LLMRequest.metadata for provider-side tracing."""
        return {
            "skill_ids": ",".join(self.skill_ids),
            "skill_versions": ",".join(self.skill_versions),
            "skill_checksums": ",".join(self.skill_checksums),
            "skill_task_type": self.task_type,
            "skill_slide_type": self.slide_type or "",
            "skill_project_type": self.project_type or "",
            "skill_audience": self.audience or "",
        }

    @classmethod
    def from_skills(
        cls,
        skills: list[ArchiumSkillDefinition],
        *,
        task_type: str,
        slide_type: str | None = None,
        project_type: str | None = None,
        audience: str | None = None,
    ) -> SkillInvocationAudit:
        return cls(
            task_type=task_type,
            slide_type=slide_type,
            project_type=project_type,
            audience=audience,
            skill_ids=[skill.id for skill in skills],
            skill_versions=[skill.version for skill in skills],
            skill_checksums=[skill.checksum for skill in skills],
            prompt_uris=[skill.prompt_uri for skill in skills],
        )
