"""Snapshot helpers for revision-tracked presentation artifacts."""

from __future__ import annotations

from archium.domain.presentation import PresentationBrief, Storyline


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
