"""Map LLM concept direction drafts to domain models."""

from __future__ import annotations

from uuid import UUID

from archium.domain.concept_direction import ConceptDirection
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.enums import ConceptDirectionStatus
from archium.infrastructure.llm.concept_direction_schemas import ConceptDirectionDraft


def concept_direction_from_draft(
    draft: ConceptDirectionDraft,
    *,
    project_id: UUID,
    exploration_session_id: UUID | None = None,
    mission_id: UUID | None = None,
    sort_order: int = 0,
) -> ConceptDirection:
    visual = None
    if draft.visual_prompt is not None:
        vp = draft.visual_prompt
        visual = ConceptVisualPrompt(
            image_prompt=(vp.image_prompt or "").strip(),
            camera=(vp.camera or "").strip(),
            style=(vp.style or "").strip(),
        )
        if visual.is_empty():
            visual = None
    return ConceptDirection(
        project_id=project_id,
        exploration_session_id=exploration_session_id,
        mission_id=mission_id,
        title=draft.title.strip(),
        summary=draft.summary.strip(),
        theme=(draft.theme or "").strip(),
        spatial_idea=(draft.spatial_idea or "").strip(),
        spatial_strategy=(draft.spatial_strategy or "").strip(),
        formal_language=(draft.formal_language or "").strip(),
        material_strategy=(draft.material_strategy or "").strip(),
        reference_dna=[
            item.strip() for item in draft.reference_dna if item and item.strip()
        ],
        visual_prompt=visual,
        experience_focus=(draft.experience_focus or "").strip(),
        differentiator=(draft.differentiator or "").strip(),
        open_questions=[item.strip() for item in draft.open_questions if item.strip()],
        risks=[item.strip() for item in draft.risks if item.strip()],
        status=ConceptDirectionStatus.DRAFT,
        sort_order=sort_order,
        source="generated",
    )
