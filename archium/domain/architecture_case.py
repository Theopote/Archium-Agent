"""Architecture case — semantic reference for research / concept (not image RAG)."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.design_knowledge import DesignKnowledge


class ArchitectureCase(DomainModel):
    """Why a project is worth studying — not a brochure dump."""

    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1)
    architect: str = ""
    location: str = ""
    year: str = ""
    building_type: str = ""
    context: str = ""
    design_problem: str = Field(
        default="",
        description="What contradiction / need the project addresses.",
    )
    strategy: str = Field(
        default="",
        description="Core architectural strategy (one line).",
    )
    spatial_logic: str = Field(
        default="",
        description="How space is organized (path, courtyard, embed…).",
    )
    material_language: str = ""
    atmosphere: str = ""
    transferable_principles: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(
        default_factory=list,
        description="Semantic tags for cross-type retrieval (meditation, terrace…).",
    )

    def to_prompt_block(self) -> str:
        lines = [f"案例：{self.name}"]
        if self.architect.strip():
            lines.append(f"建筑师：{self.architect.strip()}")
        meta = " · ".join(
            part
            for part in (self.location, self.year, self.building_type)
            if part and str(part).strip()
        )
        if meta:
            lines.append(meta)
        if self.design_problem.strip():
            lines.append(f"设计问题：{self.design_problem.strip()}")
        if self.strategy.strip():
            lines.append(f"核心策略：{self.strategy.strip()}")
        if self.spatial_logic.strip():
            lines.append(f"空间逻辑：{self.spatial_logic.strip()}")
        if self.material_language.strip():
            lines.append(f"材料语言：{self.material_language.strip()}")
        if self.atmosphere.strip():
            lines.append(f"氛围：{self.atmosphere.strip()}")
        if self.transferable_principles:
            lines.append(
                "可迁移原则：\n"
                + "\n".join(
                    f"- {item.strip()}"
                    for item in self.transferable_principles
                    if item.strip()
                )
            )
        if self.risks:
            lines.append(
                "风险/边界：\n"
                + "\n".join(f"- {item.strip()}" for item in self.risks if item.strip())
            )
        return "\n".join(lines)

    def to_design_knowledge(self) -> DesignKnowledge:
        """Map case into DesignKnowledge for Concept / Critique consumption."""
        principle = ""
        if self.transferable_principles:
            principle = self.transferable_principles[0].strip()
        elif self.strategy.strip():
            principle = self.strategy.strip()
        return DesignKnowledge(
            topic=self.name,
            insight=(self.design_problem or self.strategy or self.name).strip(),
            principle=principle,
            spatial_translation=(self.spatial_logic or "").strip(),
            material_strategy=(self.material_language or "").strip(),
            project_link=f"参照基因：{self.name}"
            + (f"（{self.architect}）" if self.architect.strip() else ""),
            applicability="；".join(self.risks[:3]) if self.risks else "跨类型迁移时需校验气候/尺度/制度",
            evidence=[
                bit
                for bit in (
                    self.name,
                    self.architect,
                    f"{self.location} {self.year}".strip(),
                )
                if bit and str(bit).strip()
            ],
        )
