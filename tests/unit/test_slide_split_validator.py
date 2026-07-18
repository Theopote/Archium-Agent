"""Unit tests for SlideSplitPlan structural validation."""

from __future__ import annotations

from uuid import uuid4

from archium.application.slide_split_planner import build_split_plan
from archium.application.slide_split_validator import validate_split_plan
from archium.domain.citation import Citation
from archium.domain.enums import SlideStatus, SlideType, VisualType
from archium.domain.presentation import Chapter, Storyline
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.slide_split import GENERIC_CONTINUATION_MESSAGE, SlideSplitPlan


def _slide(**overrides: object) -> SlideSpec:
    defaults: dict[str, object] = {
        "presentation_id": uuid4(),
        "chapter_id": "ch-traffic",
        "order": 1,
        "title": "交通组织",
        "message": "人车混行导致通行效率低。",
        "slide_type": SlideType.CONTENT,
        "status": SlideStatus.PLANNED,
    }
    defaults.update(overrides)
    return SlideSpec.model_construct(**defaults)  # type: ignore[arg-type]


def _storyline(*, estimated: int = 4) -> Storyline:
    return Storyline(
        presentation_id=uuid4(),
        thesis="交通重组",
        chapters=[
            Chapter(
                id="ch-traffic",
                title="交通组织",
                purpose="说明现状",
                key_message="冲突严重",
                order=0,
                estimated_slide_count=estimated,
            )
        ],
    )


class TestSlideSplitValidator:
    def test_narrative_coherent_split_passes_validation(self) -> None:
        original = _slide(
            key_points=[
                "现状：人车混行 35%",
                "原因：落客区不足",
                "策略一：分离动线",
                "策略二：缓冲落客",
                "策略三：分时货运",
                "策略四：引导标识",
            ]
        )
        updated = original.model_copy(update={"key_points": original.key_points[:5]})
        moved = original.key_points[5:]

        plan = build_split_plan(
            original,
            updated,
            moved,
            "要点超过 5 条",
            storyline=_storyline(),
            chapter_slide_count=3,
        )

        assert not plan.requires_human_approval
        assert plan.validation_issues == []
        assert plan.primary_continuation.message == moved[0]

    def test_generic_multi_point_continuation_requires_approval(self) -> None:
        original = _slide(key_points=["补充说明", "其他背景", "第三点"])
        updated = original.model_copy(update={"key_points": ["补充说明"]})
        moved = ["其他背景", "第三点"]
        continuation = _slide(
            id=uuid4(),
            order=2,
            title="交通组织（续）",
            message=GENERIC_CONTINUATION_MESSAGE,
            key_points=moved,
        )
        plan = SlideSplitPlan(
            reason="测试",
            source_slide_id=original.id,
            new_slides=[updated, continuation],
        )

        validated = validate_split_plan(plan, original=original)

        assert validated.requires_human_approval
        assert any("占位核心信息" in issue for issue in validated.validation_issues)

    def test_evidence_separated_from_citations_requires_approval(self) -> None:
        citation = Citation(
            document_id=uuid4(),
            document_name="规划.pdf",
            quote="人车混行比例 35%",
        )
        original = _slide(
            key_points=["一般描述", "床位规模 500 张"],
            source_citations=[citation],
        )
        updated = original.model_copy(
            update={"key_points": ["一般描述"], "source_citations": [citation]}
        )
        moved = ["床位规模 500 张"]
        continuation = _slide(
            id=uuid4(),
            order=2,
            title="交通组织 — 补充说明",
            message="床位规模 500 张",
            key_points=moved,
            source_citations=[],
        )
        plan = SlideSplitPlan(
            reason="测试",
            source_slide_id=original.id,
            new_slides=[updated, continuation],
        )

        validated = validate_split_plan(plan, original=original)

        assert validated.requires_human_approval
        assert any(
            "引用仍留在原页" in issue or "未分配引用" in issue
            for issue in validated.validation_issues
        )

    def test_storyline_budget_exceeded_requires_approval(self) -> None:
        original = _slide(key_points=[f"要点 {index}" for index in range(6)])
        updated = original.model_copy(update={"key_points": original.key_points[:5]})
        moved = original.key_points[5:]

        plan = build_split_plan(
            original,
            updated,
            moved,
            "要点溢出",
            storyline=_storyline(estimated=2),
            chapter_slide_count=3,
        )

        assert plan.requires_human_approval
        assert any("Storyline 预算" in issue for issue in plan.validation_issues)

    def test_asset_mapping_covers_all_visuals(self) -> None:
        original = _slide(
            key_points=[f"要点 {index}" for index in range(6)],
            visual_requirements=[
                VisualRequirement(type=VisualType.DIAGRAM, description="流线 A"),
                VisualRequirement(type=VisualType.DIAGRAM, description="流线 B"),
            ],
        )
        updated = original.model_copy(update={"key_points": original.key_points[:5]})
        moved = original.key_points[5:]

        plan = build_split_plan(
            original,
            updated,
            moved,
            "要点溢出",
            storyline=_storyline(),
            chapter_slide_count=3,
        )

        assert set(plan.asset_mapping.keys()) == set(range(len(original.visual_requirements)))
        assert not any("视觉素材" in issue for issue in plan.validation_issues)

    def test_citation_stays_on_source_when_evidence_did_not_move(self) -> None:
        original = _slide(
            key_points=[
                "现状：人车混行 35%",
                "原因：落客区不足",
                "策略一：分离人车动线",
                "策略二：增设落客缓冲",
                "策略三：优化货运时段",
            ],
            source_citations=[
                Citation(
                    document_id=uuid4(),
                    document_name="规划.pdf",
                    quote="人车混行比例 35%",
                )
            ],
        )
        updated = original.model_copy(update={"key_points": original.key_points[:3]})
        moved = original.key_points[3:]

        plan = build_split_plan(
            original,
            updated,
            moved,
            "要点溢出",
            storyline=_storyline(),
            chapter_slide_count=3,
        )

        assert not plan.requires_human_approval
        assert not any("引用仍留在原页" in issue for issue in plan.validation_issues)
