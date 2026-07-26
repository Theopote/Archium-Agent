"""Structured design intent for concept exploration projects."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.design_rationale import DesignRationale
from archium.domain.intent.intent_evidence import IntentEvidence
from archium.domain.spatial_design import DesignRule, SpatialIntent


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
    evidence: list[IntentEvidence] = Field(default_factory=list)
    design_rationale: DesignRationale | None = None
    spatial_intent: SpatialIntent | None = None
    design_rules: list[DesignRule] = Field(default_factory=list)
    # DOM-024: provenance to ConceptDirection when Intent was projected from one.
    source_direction_id: UUID | None = Field(
        default=None,
        description="ConceptDirection id this intent was last projected from (if any).",
    )

    def with_evidence(
        self,
        *items: IntentEvidence,
        max_items: int = 40,
    ) -> DesignIntent:
        """Append unique evidence entries (by statement + source_type)."""
        merged = list(self.evidence)
        seen = {(entry.statement.strip(), entry.source_type.value) for entry in merged}
        for item in items:
            statement = item.statement.strip()
            if not statement:
                continue
            key = (statement, item.source_type.value)
            if key in seen:
                continue
            merged.append(item.model_copy(update={"statement": statement}))
            seen.add(key)
        return self.model_copy(update={"evidence": merged[-max_items:]})

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
        if self.evidence:
            lines: list[str] = []
            for entry in self.evidence[-8:]:
                conf = int(round(entry.confidence * 100))
                lines.append(
                    f"- [{entry.source_label()} {conf}%] {entry.statement.strip()}"
                )
            sections.append("意图出处:\n" + "\n".join(lines))
        if self.design_rationale is not None:
            block = self.design_rationale.to_prompt_block()
            if block.strip():
                sections.append(block)
        if self.spatial_intent is not None:
            block = self.spatial_intent.to_prompt_block()
            if block.strip():
                sections.append(block)
        if self.design_rules:
            rule_lines = [
                f"- {rule.to_prompt_line()}"
                for rule in self.design_rules
                if not rule.is_empty()
            ]
            if rule_lines:
                sections.append("设计规则：\n" + "\n".join(rule_lines))
        return "\n".join(sections)
