"""Unit tests for explicit page→asset bindings."""

from __future__ import annotations

from uuid import uuid4

from archium.application.slide_asset_binding_service import apply_slide_asset_bindings
from archium.application.slide_plan_slots import build_slide_plan_slots
from archium.domain.enums import PresentationType, SlideAssetBindingRole, VisualType
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Chapter, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.slide_asset_binding import (
    SlideAssetBinding,
    format_page_asset_bindings_block,
    slide_asset_bindings_from_page_materials,
)
from archium.prompts.slide_planning import build_single_slide_plan_user_prompt


def test_page_materials_parse_dict_and_infer_role() -> None:
    asset_id = uuid4()
    bindings = slide_asset_bindings_from_page_materials(
        {
            2: [
                {
                    "asset_id": str(asset_id),
                    "type": "drawing",
                    "filename": "masterplan.png",
                    "description": "总平面图",
                }
            ],
            4: [{"asset_id": str(asset_id), "type": "excel", "description": "指标表"}],
        }
    )
    assert len(bindings) == 2
    assert bindings[0].page_order == 2
    assert bindings[0].binding_role == SlideAssetBindingRole.PRIMARY_DRAWING
    assert bindings[0].user_description == "总平面图"
    assert bindings[1].binding_role == SlideAssetBindingRole.METRIC_SOURCE


def test_apply_bindings_confirm_and_create_requirement() -> None:
    slide_id = uuid4()
    asset_id = uuid4()
    slides = [
        SlideSpec(
            id=slide_id,
            presentation_id=uuid4(),
            chapter_id="ch1",
            order=2,
            title="入口",
            message="人车混行是主因",
            visual_requirements=[],
        )
    ]
    bindings = [
        SlideAssetBinding(
            page_order=2,
            asset_id=asset_id,
            binding_role=SlideAssetBindingRole.PROJECT_PHOTO,
            user_description="入口照片",
            required=True,
        )
    ]

    updated, resolved, applied = apply_slide_asset_bindings(slides, bindings)

    assert applied == 1
    assert resolved[0].slide_id == slide_id
    req = updated[0].visual_requirements[0]
    assert req.type == VisualType.SITE_PHOTO
    assert req.preferred_asset_ids == [asset_id]
    assert req.confirmed is True
    assert req.required is True
    assert "user_binding:project_photo" in req.processing_instructions[0]


def test_apply_bindings_override_unconfirmed_match() -> None:
    asset_user = uuid4()
    asset_auto = uuid4()
    slides = [
        SlideSpec(
            presentation_id=uuid4(),
            chapter_id="ch1",
            order=0,
            title="总图",
            message="总平面控制结构",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面",
                    preferred_asset_ids=[asset_auto],
                    confirmed=False,
                )
            ],
        )
    ]
    bindings = [
        SlideAssetBinding(
            page_order=0,
            asset_id=asset_user,
            binding_role=SlideAssetBindingRole.PRIMARY_DRAWING,
            user_description="用户指定总平面",
        )
    ]

    updated, _, applied = apply_slide_asset_bindings(slides, bindings)
    assert applied == 1
    req = updated[0].visual_requirements[0]
    assert req.preferred_asset_ids == [asset_user]
    assert req.confirmed is True


def test_slots_include_asset_bindings_text() -> None:
    presentation_id = uuid4()
    asset_id = uuid4()
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="更新",
        audience="院领导",
        purpose="决策",
        core_message="改善交通",
        target_slide_count=2,
        presentation_type=PresentationType.CLIENT_REVIEW,
    )
    storyline = Storyline(
        presentation_id=presentation_id,
        thesis="交通",
        chapters=[
            Chapter(
                id="ch1",
                title="现状",
                purpose="问题",
                key_message="人车混行",
                order=0,
                estimated_slide_count=2,
            )
        ],
    )
    outline = OutlinePlan(
        presentation_id=presentation_id,
        title=brief.title,
        thesis="交通",
        audience=brief.audience,
        purpose=brief.purpose,
        sections=[
            OutlineSection(
                id="ch1",
                title="现状",
                purpose="问题",
                key_message="人车混行",
                order=0,
                estimated_slide_count=2,
            )
        ],
        page_asset_bindings=[
            SlideAssetBinding(
                page_order=0,
                asset_id=asset_id,
                binding_role=SlideAssetBindingRole.PRIMARY_DRAWING,
                user_description="总平面图",
            )
        ],
    )
    slots = build_slide_plan_slots(brief, storyline, outline=outline)
    assert len(slots[0].asset_bindings) == 1
    assert "页面素材绑定" in slots[0].asset_bindings_text
    prompt = build_single_slide_plan_user_prompt(
        slot_chapter_id="ch1",
        slot_order=0,
        deck_position=0,
        deck_total=2,
        slide_context="ctx",
        brief_summary="brief",
        storyline_summary="story",
        asset_bindings=slots[0].asset_bindings_text,
    )
    assert "必须优先使用" in prompt
    assert format_page_asset_bindings_block(list(slots[0].asset_bindings))
