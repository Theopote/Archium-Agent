"""Tests for layout family registry and deterministic generators."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual import (
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
    VisualIntent,
    default_presentation_design_system,
)
from archium.domain.visual.enums import CropPolicy, ImageFit
from archium.infrastructure.layout.generators.base import (
    LayoutGeneratorContext,
    content_from_slide,
)
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.layout.layout_solver import LayoutSolver


def _slide(**overrides: object) -> SlideSpec:
    defaults: dict[str, object] = {
        "presentation_id": uuid4(),
        "chapter_id": "ch1",
        "order": 0,
        "title": "测试标题",
        "message": "这是一个核心结论。",
        "key_points": ["要点一", "要点二", "要点三"],
        "visual_requirements": [
            VisualRequirement(type=VisualType.SITE_PLAN, description="总平面")
        ],
    }
    defaults.update(overrides)
    return SlideSpec(**defaults)  # type: ignore[arg-type]


def _intent(slide: SlideSpec, content: VisualContentType, family: LayoutFamily) -> VisualIntent:
    return VisualIntent(
        slide_id=slide.id,
        communication_goal="测试沟通目标",
        audience_takeaway=slide.message,
        visual_priority="title > hero",
        dominant_content_type=content,
        preferred_layout_families=[family],
        hero_asset_id=uuid4(),
        supporting_asset_ids=[uuid4(), uuid4(), uuid4()],
        reading_order=["title", "hero", "source"],
    )


def _context(
    family: LayoutFamily,
    *,
    content_type: VisualContentType,
    variant: str | None = None,
    slide: SlideSpec | None = None,
) -> LayoutGeneratorContext:
    slide = slide or _slide()
    intent = _intent(slide, content_type, family)
    design = default_presentation_design_system()
    registry = get_layout_family_registry()
    resolved = registry.resolve_variant(family, variant)
    return LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content_from_slide(slide, intent, source_text="项目任务书.pdf"),
        variant=resolved,
    )


class TestLayoutFamilyRegistry:
    def test_ten_families_registered(self) -> None:
        registry = get_layout_family_registry()
        assert len(registry.all()) == 10
        assert len(registry.implemented()) == 10

    def test_drawing_focus_candidates(self) -> None:
        registry = get_layout_family_registry()
        candidates = registry.candidates_for(VisualContentType.SITE_PLAN, asset_count=1)
        assert candidates[0].family == LayoutFamily.DRAWING_FOCUS

    def test_process_and_metrics_candidates(self) -> None:
        registry = get_layout_family_registry()
        process = registry.candidates_for(VisualContentType.PROCESS, asset_count=0)
        assert process[0].family == LayoutFamily.PROCESS_NARRATIVE
        metrics = registry.candidates_for(VisualContentType.METRICS, asset_count=0)
        assert metrics[0].family == LayoutFamily.METRIC_DASHBOARD


class TestGenerators:
    def test_drawing_focus_protects_drawing(self) -> None:
        solver = LayoutSolver()
        plan = solver.generate(
            LayoutFamily.DRAWING_FOCUS,
            _context(LayoutFamily.DRAWING_FOCUS, content_type=VisualContentType.SITE_PLAN),
        )
        assert plan.layout_family == LayoutFamily.DRAWING_FOCUS
        assert plan.elements_by_role(LayoutElementRole.TITLE)
        assert plan.elements_by_role(LayoutElementRole.SOURCE)
        hero = plan.element_by_id("hero")
        assert hero is not None
        assert hero.fit_mode == ImageFit.CONTAIN
        assert hero.crop_policy == CropPolicy.FORBIDDEN
        assert all(el.x >= 0 and el.y >= 0 for el in plan.elements)
        assert all(
            el.x + el.width <= plan.page_width + 1e-6
            and el.y + el.height <= plan.page_height + 1e-6
            for el in plan.elements
        )

    def test_evidence_board_grid(self) -> None:
        slide = _slide(
            title="患者就医过程中的高压力节点",
            message="焦虑来自入口混乱、路径不清和长时间候诊。",
            key_points=["入口混乱", "路径不清", "候诊过长", "信息缺失"],
            visual_requirements=[
                VisualRequirement(type=VisualType.SITE_PHOTO, description=f"照片{i}")
                for i in range(4)
            ],
        )
        solver = LayoutSolver()
        plan = solver.generate(
            LayoutFamily.EVIDENCE_BOARD,
            _context(
                LayoutFamily.EVIDENCE_BOARD,
                content_type=VisualContentType.PHOTO_EVIDENCE,
                slide=slide,
            ),
        )
        photos = plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
        assert len(photos) == 4
        widths = {round(photo.width, 3) for photo in photos}
        assert len(widths) == 1

    def test_comparative_matrix_equal_columns(self) -> None:
        solver = LayoutSolver()
        plan = solver.generate(
            LayoutFamily.COMPARATIVE_MATRIX,
            _context(
                LayoutFamily.COMPARATIVE_MATRIX,
                content_type=VisualContentType.COMPARISON,
            ),
        )
        images = plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
        assert len(images) == 3
        assert len({round(img.width, 3) for img in images}) == 1
        assert plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)

    def test_process_narrative_steps(self) -> None:
        slide = _slide(
            title="实施路径",
            message="分三阶段推进院区更新。",
            key_points=["近期交通重组", "中期功能置换", "远期空间织补"],
            visual_requirements=[
                VisualRequirement(type=VisualType.TIMELINE, description="分期")
            ],
        )
        plan = LayoutSolver().generate(
            LayoutFamily.PROCESS_NARRATIVE,
            _context(
                LayoutFamily.PROCESS_NARRATIVE,
                content_type=VisualContentType.PROCESS,
                variant="steps_horizontal",
                slide=slide,
            ),
        )
        bodies = plan.elements_by_role(LayoutElementRole.BODY_TEXT)
        assert len(bodies) == 3

    def test_metric_dashboard_cards(self) -> None:
        slide = _slide(
            title="核心指标",
            message="更新后公服可达性显著提升。",
            key_points=["绿地率 42%", "容积率 1.8", "服务半径 500m", "床位 800"],
            visual_requirements=[
                VisualRequirement(type=VisualType.CHART, description="指标")
            ],
        )
        plan = LayoutSolver().generate(
            LayoutFamily.METRIC_DASHBOARD,
            _context(
                LayoutFamily.METRIC_DASHBOARD,
                content_type=VisualContentType.METRICS,
                slide=slide,
            ),
        )
        assert len(plan.elements_by_role(LayoutElementRole.METRIC)) >= 3

    def test_analytical_diagram_protects_aspect(self) -> None:
        plan = LayoutSolver().generate(
            LayoutFamily.ANALYTICAL_DIAGRAM,
            _context(
                LayoutFamily.ANALYTICAL_DIAGRAM,
                content_type=VisualContentType.ANALYTICAL_DIAGRAM,
                variant="diagram_with_callouts",
            ),
        )
        hero = plan.element_by_id("hero")
        assert hero is not None
        assert hero.fit_mode == ImageFit.CONTAIN
        assert hero.crop_policy == CropPolicy.FORBIDDEN
        assert plan.elements_by_role(LayoutElementRole.ANNOTATION)

    def test_all_ten_generators_emit_title(self) -> None:
        solver = LayoutSolver()
        mapping = [
            (LayoutFamily.HERO, VisualContentType.HERO_IMAGE),
            (LayoutFamily.EVIDENCE_BOARD, VisualContentType.PHOTO_EVIDENCE),
            (LayoutFamily.DRAWING_FOCUS, VisualContentType.SITE_PLAN),
            (LayoutFamily.COMPARATIVE_MATRIX, VisualContentType.COMPARISON),
            (LayoutFamily.PROCESS_NARRATIVE, VisualContentType.PROCESS),
            (LayoutFamily.ANALYTICAL_DIAGRAM, VisualContentType.ANALYTICAL_DIAGRAM),
            (LayoutFamily.METRIC_DASHBOARD, VisualContentType.METRICS),
            (LayoutFamily.STRATEGY_CARDS, VisualContentType.TEXT_ARGUMENT),
            (LayoutFamily.TEXTUAL_ARGUMENT, VisualContentType.TEXT_ARGUMENT),
            (LayoutFamily.HYBRID_CANVAS, VisualContentType.MIXED),
        ]
        assert len(solver.supported_families()) == 10
        for family, content in mapping:
            plan = solver.generate(family, _context(family, content_type=content))
            assert plan.elements_by_role(LayoutElementRole.TITLE)
            assert plan.reading_order
            assert plan.layout_family == family

    def test_title_band_avoids_text_overflow(self) -> None:
        design = default_presentation_design_system()
        slide = _slide(title="院区总平面与改造范围说明页")
        plan = LayoutSolver().generate(
            LayoutFamily.DRAWING_FOCUS,
            _context(LayoutFamily.DRAWING_FOCUS, content_type=VisualContentType.SITE_PLAN, slide=slide),
        )
        report = LayoutValidationService().validate(plan, design, require_source=False)
        title_issues = [
            issue
            for issue in report.issues
            if issue.rule_code == "LAYOUT.TEXT_OVERFLOW" and "title" in issue.element_ids
        ]
        assert not title_issues