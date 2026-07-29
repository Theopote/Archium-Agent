"""SlideSpec semantic evidence_items field."""

from __future__ import annotations

from uuid import UUID

from archium.application._helpers import slide_from_draft
from archium.domain.slide import SlideSpec
from archium.domain.visual.layout_evidence_item import EvidenceItemRole, LayoutEvidenceItem
from archium.infrastructure.llm.presentation_schemas import SlideDraft, SlideEvidenceItemDraft


class TestSlideSpecEvidenceItems:
    def test_slide_from_draft_maps_evidence_items(self) -> None:
        draft = SlideDraft(
            chapter_id="site",
            order=2,
            title="现场问题",
            message="入口混行影响到达体验。",
            evidence_items=[
                SlideEvidenceItemDraft(
                    claim="入口混行导致人车冲突",
                    role="primary",
                    focus="主入口",
                ),
                SlideEvidenceItemDraft(
                    claim="停车占道压缩人行空间",
                    role="supporting",
                ),
            ],
        )
        slide = slide_from_draft(
            draft,
            presentation_id=UUID("11111111-1111-1111-1111-111111111111"),
            session=None,  # type: ignore[arg-type]
        )
        assert len(slide.evidence_items) == 2
        assert slide.evidence_items[0].role == EvidenceItemRole.PRIMARY
        assert slide.key_points == [
            "入口混行导致人车冲突",
            "停车占道压缩人行空间",
        ]

    def test_slide_spec_roundtrip_json(self) -> None:
        slide = SlideSpec(
            presentation_id=UUID("11111111-1111-1111-1111-111111111111"),
            chapter_id="site",
            order=1,
            title="现场问题",
            message="入口混行影响到达体验。",
            evidence_items=[
                LayoutEvidenceItem(claim="混行", role=EvidenceItemRole.PRIMARY, asset="asset-1"),
            ],
        )
        restored = SlideSpec.model_validate(slide.model_dump(mode="json"))
        assert restored.evidence_items[0].claim == "混行"
        assert restored.evidence_items[0].asset == "asset-1"
