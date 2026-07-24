"""Structured design intent for concept exploration projects."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class DesignIntent(DomainModel):
    """Why the project exists and what experience it should create."""

    theme: str = ""
    problem_statement: str = ""
    social_background: str = ""
    cultural_context: str = ""
    target_users: list[str] = Field(default_factory=list)
    desired_experience: str = ""
    core_questions: list[str] = Field(default_factory=list)
    research_needed: list[str] = Field(default_factory=list)
    working_assumptions: list[str] = Field(default_factory=list)

    def to_prompt_block(self) -> str:
        """Compact text for LLM narrative / brief context."""
        sections: list[str] = []
        if self.theme.strip():
            sections.append(f"主题: {self.theme.strip()}")
        if self.problem_statement.strip():
            sections.append(f"问题陈述: {self.problem_statement.strip()}")
        if self.social_background.strip():
            sections.append(f"社会背景: {self.social_background.strip()}")
        if self.cultural_context.strip():
            sections.append(f"文化语境: {self.cultural_context.strip()}")
        if self.target_users:
            sections.append("目标用户: " + "、".join(self.target_users))
        if self.desired_experience.strip():
            sections.append(f"期望体验: {self.desired_experience.strip()}")
        if self.core_questions:
            sections.append(
                "核心追问:\n" + "\n".join(f"- {q}" for q in self.core_questions if q.strip())
            )
        if self.research_needed:
            sections.append(
                "待研究:\n" + "\n".join(f"- {q}" for q in self.research_needed if q.strip())
            )
        if self.working_assumptions:
            sections.append(
                "工作假设:\n" + "\n".join(f"- {a}" for a in self.working_assumptions if a.strip())
            )
        return "\n".join(sections)
