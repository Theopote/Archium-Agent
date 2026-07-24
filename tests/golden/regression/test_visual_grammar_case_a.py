"""Golden structure checks for Visual Grammar on case_a (VG-002)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.visual.visual_grammar_intent import forbidden_families_for_intent
from archium.application.visual.visual_grammar_recognition import recognize_page_archetype
from archium.application.visual.visual_grammar_slots import ensure_evidence_slots_on_slide
from archium.domain.enums import SlideType, VisualType
from archium.domain.slide import SlideSpec, SlideVisualRequirement
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.visual_grammar import PageArchetype, get_recipe
from archium.domain.visual.visual_intent import VisualIntent

pytestmark = pytest.mark.regression

_CASE_A = Path(__file__).resolve().parents[1] / "regression" / "cases" / "case_a_hospital.json"


def test_case_a_opening_and_diagnosis_grammar_contracts() -> None:
    """Hospital case: opening story + problem diagnosis must honor recipes."""
    assert _CASE_A.is_file()

    opening = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="医院老院区更新开篇",
        message="历史院区面临流线交叉与空间矛盾，更新目标是可持续运营。",
        slide_type=SlideType.CONTENT,
        key_points=["历史语境", "现状矛盾", "空间问题", "更新目标"],
        visual_requirements=[
            SlideVisualRequirement(type=VisualType.SITE_PHOTO, description="历史照片"),
        ],
    )
    opening_rec = recognize_page_archetype(opening)
    assert opening_rec.archetype == PageArchetype.NARRATIVE_OPENING
    stamped_opening = ensure_evidence_slots_on_slide(
        opening,
        archetype=opening_rec.archetype,
        recipe=opening_rec.recipe,
    )
    assert len(stamped_opening.required_evidence_slots) >= 3
    roles = set(stamped_opening.required_evidence_slots)
    assert "historic_or_context_photo" in roles
    assert "renewal_goal" in roles

    diagnosis = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=3,
        title="现状问题诊断",
        message="急诊流线交叉导致拥堵，后勤通道老化。",
        slide_type=SlideType.IMAGE,
        key_points=["问题1：流线交叉", "问题2：后勤老化"],
        visual_requirements=[
            SlideVisualRequirement(type=VisualType.SITE_PHOTO, description="现场照片1"),
            SlideVisualRequirement(type=VisualType.SITE_PHOTO, description="现场照片2"),
        ],
    )
    diagnosis_rec = recognize_page_archetype(diagnosis)
    assert diagnosis_rec.archetype == PageArchetype.SITE_PROBLEM_DIAGNOSIS
    recipe = get_recipe(PageArchetype.SITE_PROBLEM_DIAGNOSIS)
    assert LayoutFamily.EVIDENCE_BOARD in recipe.preferred_layout_families
    assert LayoutFamily.STRATEGY_CARDS in recipe.forbidden_layout_families

    intent = VisualIntent(
        slide_id=diagnosis.id,
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        communication_goal="诊断",
        audience_takeaway="问题清晰",
        visual_priority="photos",
        dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
    )
    forbidden = forbidden_families_for_intent(intent)
    assert LayoutFamily.STRATEGY_CARDS in forbidden
    assert LayoutFamily.HERO in forbidden
