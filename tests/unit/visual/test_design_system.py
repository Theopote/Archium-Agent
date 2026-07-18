"""Unit tests for DesignSystem and related visual domain models."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.enums import ApprovalStatus
from archium.domain.visual import (
    ArtDirection,
    DesignSystem,
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    VisualContentType,
    VisualIntent,
    default_presentation_design_system,
)
from archium.domain.visual.enums import LayoutContentType
from pydantic import ValidationError


class TestDesignSystem:
    def test_default_system_is_valid(self) -> None:
        system = default_presentation_design_system()
        assert system.page.width == 10.0
        assert system.page.height == 5.625
        assert system.grid.columns == 12
        assert system.typography.body.font_size == 16
        assert system.colors.primary.startswith("#")
        assert system.thresholds.min_body_font_pt == 14.0

    def test_spacing_must_be_non_decreasing(self) -> None:
        from archium.domain.visual.design_system import SpacingSystem

        with pytest.raises(ValidationError):
            SpacingSystem(xs=0.2, sm=0.01, md=0.15, lg=0.2, xl=0.3, xxl=0.4)

    def test_margins_cannot_exceed_page(self) -> None:
        from archium.domain.visual.design_system import PageSystem

        with pytest.raises(ValidationError):
            PageSystem(
                width=10,
                height=5.625,
                margin_top=0.45,
                margin_right=6.0,
                margin_bottom=0.45,
                margin_left=6.0,
            )

    def test_color_resolve_token(self) -> None:
        system = default_presentation_design_system()
        assert system.colors.resolve("primary_text").startswith("#")
        with pytest.raises(KeyError):
            system.colors.resolve("not_a_token")

    def test_serialization_roundtrip(self) -> None:
        system = default_presentation_design_system()
        restored = DesignSystem.model_validate(system.model_dump(mode="json"))
        assert restored.name == system.name
        assert restored.typography.title.font_size == 34


class TestArtDirection:
    def test_approve(self) -> None:
        art = ArtDirection(
            project_id=uuid4(),
            concept_name="清晰路径",
            rationale="面向医疗汇报的温和清晰表达。",
            palette_strategy="低饱和蓝绿",
            typography_strategy="可读层级",
            grid_strategy="12栏",
            image_strategy="现场照片统一",
            drawing_strategy="图纸 contain",
            diagram_strategy="旅程图优先",
            annotation_strategy="编号对应",
            cover_strategy="克制封面",
            section_strategy="留白章节",
            content_strategy="按任务选版式",
            closing_strategy="结论收束",
            pacing_strategy="开-证-结",
        )
        assert art.approval_status == ApprovalStatus.DRAFT
        art.approve()
        assert art.approval_status == ApprovalStatus.APPROVED


class TestVisualIntent:
    def test_preferred_families(self) -> None:
        intent = VisualIntent(
            slide_id=uuid4(),
            communication_goal="识别高压力节点",
            audience_takeaway="入口混乱与候诊过长",
            visual_priority="journey > photos",
            dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
            preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
        )
        assert intent.preferred_layout_families[0] == LayoutFamily.EVIDENCE_BOARD


class TestLayoutPlan:
    def test_rejects_duplicate_element_ids(self) -> None:
        with pytest.raises(ValidationError):
            LayoutPlan(
                slide_id=uuid4(),
                layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
                layout_variant="lead_and_points",
                page_width=10,
                page_height=5.625,
                design_system_id=uuid4(),
                visual_intent_id=uuid4(),
                elements=[
                    LayoutElement(
                        id="title",
                        role=LayoutElementRole.TITLE,
                        content_type=LayoutContentType.TEXT,
                        x=0.7,
                        y=0.45,
                        width=8,
                        height=0.5,
                        text_content="A",
                    ),
                    LayoutElement(
                        id="title",
                        role=LayoutElementRole.BODY_TEXT,
                        content_type=LayoutContentType.TEXT,
                        x=0.7,
                        y=1.2,
                        width=8,
                        height=1.0,
                        text_content="B",
                    ),
                ],
            )

    def test_rejects_non_positive_size(self) -> None:
        with pytest.raises(ValidationError):
            LayoutElement(
                id="bad",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                x=0,
                y=0,
                width=0,
                height=1,
            )
