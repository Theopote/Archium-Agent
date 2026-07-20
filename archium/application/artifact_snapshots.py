"""Snapshot helpers for revision-tracked presentation artifacts."""

from __future__ import annotations

from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.outline import OutlinePlan


def brief_to_snapshot(brief: PresentationBrief) -> dict[str, object]:
    return {
        "id": str(brief.id),
        "lineage_id": str(brief.lineage_id),
        "logical_key": brief.logical_key,
        "presentation_id": str(brief.presentation_id),
        "title": brief.title,
        "presentation_type": brief.presentation_type.value,
        "audience": brief.audience,
        "purpose": brief.purpose,
        "duration_minutes": brief.duration_minutes,
        "target_slide_count": brief.target_slide_count,
        "core_message": brief.core_message,
        "decisions_required": list(brief.decisions_required),
        "audience_concerns": list(brief.audience_concerns),
        "tone": brief.tone,
        "required_sections": list(brief.required_sections),
        "excluded_topics": list(brief.excluded_topics),
        "language": brief.language,
        "approval_status": brief.approval_status.value,
        "version": brief.version,
    }


def storyline_to_snapshot(storyline: Storyline) -> dict[str, object]:
    return {
        "id": str(storyline.id),
        "lineage_id": str(storyline.lineage_id),
        "logical_key": storyline.logical_key,
        "presentation_id": str(storyline.presentation_id),
        "thesis": storyline.thesis,
        "narrative_pattern": storyline.narrative_pattern,
        "approval_status": storyline.approval_status.value,
        "version": storyline.version,
        "chapters": [
            {
                "id": chapter.id,
                "title": chapter.title,
                "purpose": chapter.purpose,
                "key_message": chapter.key_message,
                "order": chapter.order,
                "estimated_slide_count": chapter.estimated_slide_count,
            }
            for chapter in storyline.chapters
        ],
    }


def outline_to_snapshot(outline: OutlinePlan) -> dict[str, object]:
    return {
        "id": str(outline.id),
        "lineage_id": str(outline.lineage_id),
        "logical_key": outline.logical_key,
        "presentation_id": str(outline.presentation_id),
        "title": outline.title,
        "thesis": outline.thesis,
        "audience": outline.audience,
        "purpose": outline.purpose,
        "target_slide_count": outline.target_slide_count,
        "audience_mode": outline.audience_mode.value,
        "approval_status": outline.approval_status.value,
        "version": outline.version,
        "sections": [
            {
                "id": section.id,
                "title": section.title,
                "purpose": section.purpose,
                "key_message": section.key_message,
                "estimated_slide_count": section.estimated_slide_count,
                "evidence_requirements": list(section.evidence_requirements),
                "required_assets": list(section.required_assets),
                "required": section.required,
                "expanded": section.expanded,
                "order": section.order,
                "category": section.category,
            }
            for section in outline.sections
        ],
    }


def cultural_narrative_to_snapshot(plan: CulturalNarrativePlan) -> dict[str, object]:
    return {
        "id": str(plan.id),
        "lineage_id": str(plan.lineage_id),
        "logical_key": plan.logical_key,
        "project_id": str(plan.project_id),
        "central_story": plan.central_story,
        "identity_keywords": list(plan.identity_keywords),
        "approval_status": plan.approval_status.value,
        "version": plan.version,
        "historical_timeline_count": len(plan.historical_timeline),
        "characters_count": len(plan.characters),
        "places_count": len(plan.places),
        "communication_themes": [theme.theme for theme in plan.communication_themes],
        "unsupported_claims": list(plan.unsupported_claims),
    }


def renovation_issue_map_to_snapshot(plan: RenovationIssueMap) -> dict[str, object]:
    return {
        "id": str(plan.id),
        "lineage_id": str(plan.lineage_id),
        "logical_key": plan.logical_key,
        "project_id": str(plan.project_id),
        "building_summary": plan.building_summary,
        "approval_status": plan.approval_status.value,
        "version": plan.version,
        "evidence_count": len(plan.evidence_items),
        "issue_count": len(plan.issues),
        "strategy_count": len(plan.strategies),
        "unsupported_claims": list(plan.unsupported_claims),
    }
