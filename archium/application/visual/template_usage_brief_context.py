"""Runtime consumption helpers for bound TemplateUsageBrief contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.template_usage_brief import TemplateUsageBrief
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    TemplateUsageBriefRepository,
)


@dataclass(frozen=True)
class TemplateUsageBriefRef:
    """Immutable pointer recorded on ArtDirection / page design briefs."""

    template_usage_brief_id: UUID
    template_usage_brief_version: int


@dataclass(frozen=True)
class TemplateUsageConstraints:
    """Machine-usable constraints extracted from a bound brief."""

    brief_id: UUID
    brief_version: int
    template_id: str
    forbidden_patterns: tuple[str, ...] = ()
    drawing_fit_must_contain: bool = True
    forbid_drawing_cover_crop: bool = True
    preferred_icon_style: str = "line"
    photo_treatment_policy: str = "subtle_unify"
    content_density_hint: str = ""
    page_margins: dict[str, float] = field(default_factory=dict)
    brand_traits: tuple[str, ...] = ()
    prompt_block: str = ""


def brief_ref(brief: TemplateUsageBrief) -> TemplateUsageBriefRef:
    return TemplateUsageBriefRef(
        template_usage_brief_id=brief.id,
        template_usage_brief_version=brief.version,
    )


def bind_brief_to_art_direction(
    art: ArtDirection,
    brief: TemplateUsageBrief,
) -> ArtDirection:
    """Pin ArtDirection to a specific brief version (does not auto-follow re-induction)."""
    updated = art.model_copy(
        update={
            "template_usage_brief_id": brief.id,
            "template_usage_brief_version": brief.version,
            "version": art.version + 1,
        }
    )
    updated.touch()
    return updated


def constraints_from_brief(brief: TemplateUsageBrief) -> TemplateUsageConstraints:
    forbidden = tuple(item for item in brief.forbidden_patterns if str(item).strip())
    drawing_text = (brief.drawing_treatment or "").lower()
    must_contain = "contain" in drawing_text or brief.drawing_fit_policy == "contain"
    forbid_cover = any(
        "cover" in item.lower() or "crop" in item.lower() for item in forbidden
    ) or must_contain
    return TemplateUsageConstraints(
        brief_id=brief.id,
        brief_version=brief.version,
        template_id=brief.template_id,
        forbidden_patterns=forbidden,
        drawing_fit_must_contain=must_contain,
        forbid_drawing_cover_crop=forbid_cover,
        preferred_icon_style=brief.preferred_icon_style or "line",
        photo_treatment_policy=brief.photo_treatment_policy or "subtle_unify",
        content_density_hint=brief.content_density,
        page_margins=dict(brief.page_margins),
        brand_traits=tuple(brief.brand_traits),
        prompt_block=prompt_block_from_brief(brief),
    )


def prompt_block_from_brief(brief: TemplateUsageBrief) -> str:
    lines = [
        f"[TemplateUsageBrief id={brief.id} v{brief.version} template={brief.template_id}]",
        f"品牌：{'; '.join(brief.brand_traits[:4]) or '（未声明）'}",
        f"标题行为：{brief.title_behavior or '（未声明）'}",
        f"内容密度：{brief.content_density or '（未声明）'}",
        f"图片处理：{brief.image_treatment or brief.photo_treatment_policy}",
        f"图纸处理：{brief.drawing_treatment or brief.drawing_fit_policy}",
        f"图标风格：{brief.preferred_icon_style}",
    ]
    if brief.forbidden_patterns:
        lines.append("禁用模式：")
        lines.extend(f"- {item}" for item in brief.forbidden_patterns[:12])
    return "\n".join(lines)


def load_brief_for_art_direction(
    session: Session,
    art: ArtDirection | None,
) -> TemplateUsageBrief | None:
    """Load the **bound** brief version — not the latest induction for the template."""
    if art is None or art.template_usage_brief_id is None:
        return None
    brief = TemplateUsageBriefRepository(session).get(art.template_usage_brief_id)
    if brief is None:
        return None
    # Prefer exact id; version mismatch is still the bound snapshot (immutable row).
    return brief


def resolve_brief_for_presentation(
    session: Session,
    *,
    project_id: UUID,
    presentation_id: UUID | None,
) -> TemplateUsageBrief | None:
    arts = ArtDirectionRepository(session).list_by_project(project_id)
    selected: ArtDirection | None = None
    for art in arts:
        if presentation_id is not None and art.presentation_id == presentation_id:
            selected = art
            break
    if selected is None and arts:
        selected = arts[0]
    return load_brief_for_art_direction(session, selected)


def resolve_constraints_for_presentation(
    session: Session,
    *,
    project_id: UUID,
    presentation_id: UUID | None,
) -> TemplateUsageConstraints | None:
    brief = resolve_brief_for_presentation(
        session, project_id=project_id, presentation_id=presentation_id
    )
    if brief is None:
        return None
    return constraints_from_brief(brief)
