"""Cultural narrative detection, validation, and prompt formatting."""

from __future__ import annotations

import json
from uuid import UUID

from archium.application.outline_templates import detect_scenario_template
from archium.application.presentation_models import PresentationRequest
from archium.domain.cultural_narrative import (
    ArchitecturalSymbol,
    CommunicationTheme,
    CulturalCharacter,
    CulturalNarrativePlan,
    CulturalPlace,
    CulturalRitual,
    NarrativeEvent,
)
from archium.domain.enums import InformationOrigin, ProjectType
from archium.domain.presentation import PresentationBrief
from archium.domain.project import Project
from archium.infrastructure.llm.presentation_schemas import CulturalNarrativePlanDraft


def is_cultural_village_scenario(
    *,
    brief: PresentationBrief | None = None,
    request: PresentationRequest | None = None,
    project: Project | None = None,
) -> bool:
    """Return True when the task matches cultural village / heritage communication."""
    if project is not None and project.project_type in {
        ProjectType.CULTURE,
        ProjectType.URBAN_RENEWAL,
    }:
        if brief is not None or request is not None:
            pass
        else:
            return project.project_type == ProjectType.CULTURE

    required = list(brief.required_sections) if brief is not None else []
    purpose = (brief.purpose if brief else "") or (request.purpose if request else "")
    audience = (brief.audience if brief else "") or (request.audience if request else "")
    if request is not None:
        required = required or list(request.required_sections)
    return detect_scenario_template(
        required_sections=required,
        purpose=purpose,
        audience=audience,
    ) == "cultural_village"


def narrative_fallback_from_brief(
    brief: PresentationBrief,
    *,
    project_id: UUID,
    version: int = 1,
) -> CulturalNarrativePlan:
    """Minimal narrative scaffold when LLM is unavailable."""
    keywords = [brief.title.strip()] if brief.title.strip() else []
    keywords.extend(section for section in brief.required_sections[:3] if section.strip())
    return CulturalNarrativePlan(
        project_id=project_id,
        central_story=brief.core_message or brief.purpose,
        identity_keywords=keywords,
        emotional_arc=["认知", "共鸣", "认同"],
        visitor_storyline=["到达", "体验", "理解", "带走记忆"],
        unsupported_claims=["需补充历史资料、人物故事与建筑证据"],
        version=version,
    )


def narrative_from_draft(
    draft: CulturalNarrativePlanDraft,
    *,
    project_id: UUID,
    version: int = 1,
) -> CulturalNarrativePlan:
    return CulturalNarrativePlan(
        project_id=project_id,
        central_story=draft.central_story,
        identity_keywords=list(draft.identity_keywords),
        historical_timeline=[
            NarrativeEvent(
                id=item.id,
                year_or_period=item.year_or_period,
                event=item.event,
                origin=InformationOrigin(item.origin),
                is_legend=item.is_legend,
            )
            for item in draft.historical_timeline
        ],
        characters=[
            CulturalCharacter(
                id=item.id,
                name=item.name,
                role=item.role,
                significance=item.significance,
                origin=InformationOrigin(item.origin),
                is_legend=item.is_legend,
            )
            for item in draft.characters
        ],
        places=[
            CulturalPlace(
                id=item.id,
                name=item.name,
                significance=item.significance,
                space_type=item.space_type,
                asset_refs=list(item.asset_refs),
            )
            for item in draft.places
        ],
        rituals=[
            CulturalRitual(
                id=item.id,
                name=item.name,
                description=item.description,
                season=item.season,
                origin=InformationOrigin(item.origin),
                is_legend=item.is_legend,
            )
            for item in draft.rituals
        ],
        architectural_symbols=[
            ArchitecturalSymbol(
                id=item.id,
                name=item.name,
                building_type=item.building_type,
                cultural_meaning=item.cultural_meaning,
                asset_refs=list(item.asset_refs),
            )
            for item in draft.architectural_symbols
        ],
        emotional_arc=list(draft.emotional_arc),
        visitor_storyline=list(draft.visitor_storyline),
        communication_themes=[
            CommunicationTheme(
                id=item.id,
                theme=item.theme,
                linked_characters=list(item.linked_characters),
                linked_places=list(item.linked_places),
                linked_rituals=list(item.linked_rituals),
                linked_buildings=list(item.linked_buildings),
            )
            for item in draft.communication_themes
        ],
        unsupported_claims=list(draft.unsupported_claims),
        version=version,
    )


def validate_narrative(plan: CulturalNarrativePlan) -> list[str]:
    """Return validation issues for cultural narrative quality and safety."""
    issues: list[str] = []
    if not plan.central_story.strip():
        issues.append("缺少 central_story")
    for event in plan.historical_timeline:
        if not event.is_legend and not event.source_citations:
            issues.append(f"历史事件缺少来源：{event.event[:40]}")
    for character in plan.characters:
        if character.is_legend and character.origin != InformationOrigin.SYSTEM_INFERENCE:
            pass
        elif not character.is_legend and not character.source_citations:
            issues.append(f"人物描述缺少来源：{character.name}")
    for theme in plan.communication_themes:
        if not any(
            [
                theme.linked_characters,
                theme.linked_places,
                theme.linked_rituals,
                theme.linked_buildings,
            ]
        ):
            issues.append(f"传播主题未关联真实要素：{theme.theme[:40]}")
    return issues


def format_narrative_for_prompt(plan: CulturalNarrativePlan) -> str:
    """Compact narrative summary for downstream Storyline / Outline agents."""
    payload = {
        "central_story": plan.central_story,
        "identity_keywords": plan.identity_keywords,
        "emotional_arc": plan.emotional_arc,
        "visitor_storyline": plan.visitor_storyline,
        "unsupported_claims": plan.unsupported_claims,
        "historical_timeline": [
            {
                "period": event.year_or_period,
                "event": event.event,
                "legend": event.is_legend,
            }
            for event in plan.historical_timeline
        ],
        "characters": [
            {"name": c.name, "role": c.role, "significance": c.significance, "legend": c.is_legend}
            for c in plan.characters
        ],
        "places": [{"name": p.name, "significance": p.significance} for p in plan.places],
        "rituals": [{"name": r.name, "description": r.description} for r in plan.rituals],
        "architectural_symbols": [
            {"name": a.name, "meaning": a.cultural_meaning} for a in plan.architectural_symbols
        ],
        "communication_themes": [t.theme for t in plan.communication_themes],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
