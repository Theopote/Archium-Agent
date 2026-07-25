"""PresentationIntent — who we persuade, why, and how deep.

Complements PresentationBrief scalar fields; does not replace them.
Brief remains the persisted briefing document; intent is the persuasion contract.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.enums import OutlineAudienceMode, PresentationType, ServiceDepth


class PresentationIntent(DomainModel):
    """Audience-specific persuasion contract for one deck."""

    audience: str = Field(default="", description="Who will see this deck.")
    purpose: str = Field(default="", description="What decision or understanding we need.")
    key_message: str = Field(default="", description="Single takeaway (maps Brief.core_message).")
    persuasion_strategy: str = Field(
        default="",
        description="How we argue: value / compliance / concept novelty / …",
    )
    visual_style: str = Field(
        default="",
        description="Deck visual attitude (sparse boards / evidence-heavy / …).",
    )
    depth_level: str = Field(
        default="",
        description="ServiceDepth value or free-text depth cue.",
    )
    audience_mode: OutlineAudienceMode | None = None
    presentation_type: PresentationType = PresentationType.OTHER

    def is_empty(self) -> bool:
        return not any(
            part.strip()
            for part in (
                self.audience,
                self.purpose,
                self.key_message,
                self.persuasion_strategy,
                self.visual_style,
                self.depth_level,
            )
        )

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        lines = ["【汇报意图 PresentationIntent】"]
        if self.audience.strip():
            lines.append(f"受众：{self.audience.strip()}")
        if self.audience_mode is not None:
            lines.append(f"受众模式：{self.audience_mode.value}")
        if self.purpose.strip():
            lines.append(f"目的：{self.purpose.strip()}")
        if self.key_message.strip():
            lines.append(f"核心信息：{self.key_message.strip()}")
        if self.persuasion_strategy.strip():
            lines.append(f"说服策略：{self.persuasion_strategy.strip()}")
        if self.visual_style.strip():
            lines.append(f"视觉风格：{self.visual_style.strip()}")
        if self.depth_level.strip():
            lines.append(f"深度：{self.depth_level.strip()}")
        if self.presentation_type != PresentationType.OTHER:
            lines.append(f"汇报类型：{self.presentation_type.value}")
        return "\n".join(lines)


def default_persuasion_for_type(presentation_type: PresentationType) -> str:
    return {
        PresentationType.COMPETITION: "突出概念力度、形式创新与空间叙事，少流程说明",
        PresentationType.CLIENT_REVIEW: "强调问题—策略—体验—投资/使用价值，便于决策",
        PresentationType.CONCEPT: "聚焦设计判断与空间转译，证据服务概念而非堆砌",
        PresentationType.SCHEMATIC: "展示系统逻辑与方案可行性，图示优先于修辞",
        PresentationType.DESIGN_DEVELOPMENT: "深化技术与实施路径，保留核心设计逻辑",
        PresentationType.INTERNAL: "内部对齐：缺口、假设、下一步工作",
        PresentationType.OTHER: "按受众关切组织论证路径",
    }.get(presentation_type, "按受众关切组织论证路径")


def default_visual_style_for_type(presentation_type: PresentationType) -> str:
    return {
        PresentationType.COMPETITION: "大图少字、概念氛围与图解并重",
        PresentationType.CLIENT_REVIEW: "清晰信息层级，图文并置，可讨论决策点",
        PresentationType.CONCEPT: "概念图解与空间关系优先",
        PresentationType.SCHEMATIC: "分析图、轴测与系统图主导",
        PresentationType.DESIGN_DEVELOPMENT: "图纸与细节说明并重",
        PresentationType.INTERNAL: "工作图与清单，视觉装饰最低",
        PresentationType.OTHER: "专业克制、证据可读",
    }.get(presentation_type, "专业克制、证据可读")


def infer_audience_mode(
    audience: str,
    presentation_type: PresentationType,
) -> OutlineAudienceMode | None:
    text = audience.lower()
    if any(token in text for token in ("政府", "规委", "规划", "住建", "政府审查")):
        return OutlineAudienceMode.GOVERNMENT
    if any(token in text for token in ("投资", "基金", "财务", "董事会")):
        return OutlineAudienceMode.INVESTOR
    if any(token in text for token in ("专家", "评审", "评委", "竞赛评委")):
        return OutlineAudienceMode.EXPERT_REVIEW
    if any(token in text for token in ("社区", "居民", "公众")):
        return OutlineAudienceMode.COMMUNITY
    if any(token in text for token in ("文旅", "旅游", "文化")):
        return OutlineAudienceMode.CULTURE_TOURISM
    if presentation_type == PresentationType.INTERNAL:
        return OutlineAudienceMode.INTERNAL_DESIGN
    if presentation_type == PresentationType.COMPETITION:
        return OutlineAudienceMode.EXPERT_REVIEW
    if audience.strip():
        return OutlineAudienceMode.CLIENT
    return None


def depth_from_service_depths(depths: list[ServiceDepth] | None) -> str:
    if not depths:
        return ""
    return "、".join(d.value for d in depths[:4])
