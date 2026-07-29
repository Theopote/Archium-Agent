"""Tests for semantic layout evidence items."""

from __future__ import annotations

from uuid import UUID

from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.enums import LayoutElementRole, LayoutFamily, VisualContentType
from archium.domain.visual.layout_evidence_item import (
    EvidenceItemRole,
    LayoutEvidenceItem,
    build_evidence_items_from_legacy,
    sort_evidence_items,
)
from archium.infrastructure.layout.generators.base import (
    LayoutContentBundle,
    content_from_slide,
    resolve_layout_evidence_items,
)
from archium.infrastructure.layout.layout_solver import LayoutSolver
from archium.infrastructure.layout.generators.base import LayoutGeneratorContext
from archium.domain.visual.visual_intent import VisualIntent
from archium.domain.visual import default_presentation_design_system

_PHOTO_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000001")
_PHOTO_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-000000000002")
_PHOTO_C = UUID("cccccccc-cccc-cccc-cccc-000000000003")


class TestLayoutEvidenceItem:
    def test_build_from_legacy_assigns_roles(self) -> None:
        items = build_evidence_items_from_legacy(
            asset_refs=[str(_PHOTO_B), str(_PHOTO_C)],
            claims=["占道", "景观"],
            hero_asset_ref=str(_PHOTO_A),
        )
        assert [item.role for item in items] == [
            EvidenceItemRole.PRIMARY,
            EvidenceItemRole.SUPPORTING,
            EvidenceItemRole.SUPPORTING,
        ]
        assert items[0].asset == str(_PHOTO_A)
        assert items[0].claim == "占道"
        assert items[1].claim == "景观"

    def test_sort_evidence_items_primary_first(self) -> None:
        items = sort_evidence_items(
            [
                LayoutEvidenceItem(str(_PHOTO_B), "辅证", EvidenceItemRole.SUPPORTING),
                LayoutEvidenceItem(str(_PHOTO_A), "主证", EvidenceItemRole.PRIMARY),
                LayoutEvidenceItem(str(_PHOTO_C), "细节", EvidenceItemRole.DETAIL),
            ]
        )
        assert [item.role for item in items] == [
            EvidenceItemRole.PRIMARY,
            EvidenceItemRole.SUPPORTING,
            EvidenceItemRole.DETAIL,
        ]

    def test_content_from_slide_populates_evidence_items(self) -> None:
        slide = SlideSpec(
            presentation_id=UUID("11111111-1111-1111-1111-111111111111"),
            chapter_id="site",
            order=1,
            title="交通问题",
            message="入口混行影响到达体验。",
            key_points=["混行", "占道", "景观"],
            visual_requirements=[
                VisualRequirement(type=VisualType.SITE_PHOTO, description="入口"),
            ],
        )
        intent = VisualIntent(
            slide_id=slide.id,
            communication_goal="呈现场地问题证据",
            audience_takeaway=slide.message,
            visual_priority="photos > title",
            dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
            supporting_asset_ids=[_PHOTO_A, _PHOTO_B, _PHOTO_C],
        )
        bundle = content_from_slide(slide, intent)
        items = resolve_layout_evidence_items(bundle, limit=3)
        assert len(items) == 3
        assert items[0].claim == "混行"
        assert items[0].role == EvidenceItemRole.PRIMARY

    def test_evidence_board_uses_semantic_claims(self) -> None:
        slide = SlideSpec(
            presentation_id=UUID("11111111-1111-1111-1111-111111111111"),
            chapter_id="site",
            order=1,
            title="交通问题",
            message="入口混行影响到达体验。",
            key_points=[],
            visual_requirements=[],
        )
        intent = VisualIntent(
            slide_id=slide.id,
            communication_goal="呈现场地问题证据",
            audience_takeaway=slide.message,
            visual_priority="photos > title",
            dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        )
        content = LayoutContentBundle(
            title=slide.title,
            message=slide.message,
            evidence_items=[
                LayoutEvidenceItem(
                    asset=str(_PHOTO_A),
                    claim="入口混行导致患者与车流交织",
                    role=EvidenceItemRole.PRIMARY,
                ),
                LayoutEvidenceItem(
                    asset=str(_PHOTO_B),
                    claim="停车占道压缩人行空间",
                    role=EvidenceItemRole.SUPPORTING,
                ),
                LayoutEvidenceItem(
                    asset=str(_PHOTO_C),
                    claim="景观缺失削弱到达体验",
                    role=EvidenceItemRole.SUPPORTING,
                ),
            ],
        )
        context = LayoutGeneratorContext(
            slide=slide,
            visual_intent=intent,
            art_direction=None,
            design_system=default_presentation_design_system(),
            content=content,
            variant="hierarchical",
        )
        plan = LayoutSolver().generate(LayoutFamily.EVIDENCE_BOARD, context)
        annotation = plan.element_by_id("annotation_0")
        assert annotation is not None
        assert "入口混行导致患者与车流交织" in (annotation.text_content or "")
        photos = plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
        assert len(photos) == 3
        assert photos[0].content_ref == str(_PHOTO_A)

    def test_evidence_board_catalog_cases_use_explicit_items(self) -> None:
        from archium.domain.visual.enums import LayoutFamily
        from tests.benchmark.architectural_slides.case_catalog import FULL_CASE_CATALOG

        evidence_cases = [
            entry
            for entry in FULL_CASE_CATALOG
            if entry.definition.expected_layout_family == LayoutFamily.EVIDENCE_BOARD
        ]
        assert evidence_cases, "expected at least one evidence-board catalog case"
        for entry in evidence_cases:
            case_id = entry.definition.case_id
            assert entry.evidence_items, f"{case_id} must define explicit evidence_items"
            assets = {item.asset for item in entry.evidence_items}
            assert len(assets) == len(entry.evidence_items), f"{case_id} duplicate asset refs"
            for item in entry.evidence_items:
                assert item.claim.strip(), f"{case_id} evidence claim must not be empty"
