"""Golden visual composition cases V1–V7 (LayoutPlan + validation + preview artifacts)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.domain.citation import Citation
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual import (
    LayoutFamily,
    VisualContentType,
    default_presentation_design_system,
)
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutElementRole
from archium.infrastructure.layout.generators.base import (
    LayoutContentBundle,
    LayoutGeneratorContext,
    content_from_slide,
)
from archium.infrastructure.layout.layout_solver import LayoutSolver
from tests.golden.visual.composition.artifacts import (
    UPDATE_ENV,
    assert_or_update_baseline,
)

GOLDEN_ROOT = Path(__file__).resolve().parent
DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")


class _FakeIntentRepo:
    def __init__(self) -> None:
        self._items: dict = {}

    def save(self, intent):  # noqa: ANN001
        self._items[intent.id] = intent
        return intent

    def get(self, intent_id):  # noqa: ANN001
        return self._items.get(intent_id)


@pytest.fixture
def intent_service(monkeypatch: pytest.MonkeyPatch) -> VisualIntentService:
    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def _context(
    *,
    slide: SlideSpec,
    intent,
    design,
    variant: str,
    content: LayoutContentBundle | None = None,
) -> LayoutGeneratorContext:
    return LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content or content_from_slide(slide, intent),
        variant=variant,
    )


def test_v1_drawing_focus_site_plan(intent_service: VisualIntentService) -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="masterplan",
        order=1,
        title="总体规划与空间结构",
        message="总平面确立院落轴线与核心公服节点。",
        key_points=["绿地率 42%", "容积率 1.8", "公服半径 500m", "轴线贯通", "开放院落"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PLAN,
                description="总平面图",
                preferred_asset_ids=[uuid4()],
            )
        ],
        source_citations=[
            Citation(
                document_id=DOCUMENT_ID,
                document_name="总体规划说明书.pdf",
                page_number=12,
            )
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    assert intent.dominant_content_type == VisualContentType.SITE_PLAN
    assert LayoutFamily.DRAWING_FOCUS in intent.preferred_layout_families

    design = default_presentation_design_system()
    plan = LayoutSolver().generate(
        LayoutFamily.DRAWING_FOCUS,
        _context(slide=slide, intent=intent, design=design, variant="drawing_with_metrics"),
    )
    report = LayoutValidationService().validate(
        plan, design, require_source=True, drawing_hero=True
    )

    hero = plan.element_by_id("hero")
    assert hero is not None
    assert hero.fit_mode == ImageFit.CONTAIN
    assert hero.crop_policy == CropPolicy.FORBIDDEN
    assert plan.elements_by_role(LayoutElementRole.SOURCE)
    assert plan.elements_by_role(LayoutElementRole.TITLE)
    assert not report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / "v1_drawing_focus",
        plan=plan,
        report=report,
        design=design,
        title=slide.title,
    )


def test_v2_evidence_board_photos(intent_service: VisualIntentService) -> None:
    photos = [uuid4() for _ in range(4)]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="evidence",
        order=2,
        title="患者就医过程中的高压力节点",
        message="患者的焦虑并不只来自疾病，而来自入口混乱、路径不清和长时间候诊。",
        key_points=["入口混乱", "路径不清", "候诊过长", "问询反复"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description=f"现场照片{i + 1}",
                preferred_asset_ids=[photos[i]],
            )
            for i in range(4)
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="现场踏勘记录.pdf", page_number=3)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    assert intent.dominant_content_type == VisualContentType.PHOTO_EVIDENCE
    assert LayoutFamily.EVIDENCE_BOARD in intent.preferred_layout_families

    design = default_presentation_design_system()
    plan = LayoutSolver().generate(
        LayoutFamily.EVIDENCE_BOARD,
        _context(slide=slide, intent=intent, design=design, variant="numbered_grid"),
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)

    photos_els = plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(photos_els) == 4
    assert len({round(el.width, 3) for el in photos_els}) == 1
    assert plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert not report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / "v2_evidence_board",
        plan=plan,
        report=report,
        design=design,
        title=slide.title,
    )


def test_v3_comparative_matrix(intent_service: VisualIntentService) -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="cases",
        order=3,
        title="三个既有图书馆更新案例比较",
        message="既有图书馆更新应优先重建公共性与可达性，而非单纯扩容。",
        key_points=[
            "空间策略",
            "运营模式",
            "公众可达性",
            "案例A：中庭再生",
            "案例B：街道界面",
        ],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.COMPARISON,
                description="案例比较",
                preferred_asset_ids=[uuid4()],
            ),
            VisualRequirement(
                type=VisualType.REFERENCE_CASE,
                description="案例图1",
                preferred_asset_ids=[uuid4()],
            ),
            VisualRequirement(
                type=VisualType.REFERENCE_CASE,
                description="案例图2",
                preferred_asset_ids=[uuid4()],
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="案例研究汇编.pdf", page_number=8)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    if intent.dominant_content_type != VisualContentType.COMPARISON:
        intent.dominant_content_type = VisualContentType.COMPARISON
        intent.preferred_layout_families = [LayoutFamily.COMPARATIVE_MATRIX]

    design = default_presentation_design_system()
    plan = LayoutSolver().generate(
        LayoutFamily.COMPARATIVE_MATRIX,
        _context(slide=slide, intent=intent, design=design, variant="matrix_with_insight"),
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)

    assert plan.layout_family == LayoutFamily.COMPARATIVE_MATRIX
    images = plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(images) == 3
    assert len({round(img.width, 3) for img in images}) == 1
    assert plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert not report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / "v3_comparative_matrix",
        plan=plan,
        report=report,
        design=design,
        title=slide.title,
    )


def test_v4_analytical_diagram(intent_service: VisualIntentService) -> None:
    """V4：流线分析图 + 图例 + 三条结论 + 来源."""
    hero_id = uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="analysis",
        order=4,
        title="急诊流线与交叉冲突分析",
        message="急诊流线应分离急救、步行与后勤，减少交叉冲突。",
        key_points=[
            "急救通道与步行入口交叉",
            "候诊回流挤压抢救区",
            "后勤与污物路径未闭环",
        ],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.DIAGRAM,
                description="流线分析图",
                preferred_asset_ids=[hero_id],
            )
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="流线分析说明.pdf", page_number=5)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    intent.dominant_content_type = VisualContentType.ANALYTICAL_DIAGRAM
    intent.preferred_layout_families = [LayoutFamily.ANALYTICAL_DIAGRAM]
    intent.hero_asset_id = hero_id

    design = default_presentation_design_system()
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=list(slide.key_points),
        captions=["急救流线", "步行流线", "后勤流线", "冲突节点"],
        source_text="流线分析说明.pdf p.5",
        hero_asset_ref=str(hero_id),
        insight=slide.message,
    )
    plan = LayoutSolver().generate(
        LayoutFamily.ANALYTICAL_DIAGRAM,
        _context(
            slide=slide,
            intent=intent,
            design=design,
            variant="diagram_with_callouts",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(
        plan, design, require_source=True, drawing_hero=True
    )

    assert plan.layout_family == LayoutFamily.ANALYTICAL_DIAGRAM
    assert plan.element_by_id("hero") is not None
    assert plan.element_by_id("legend") is not None
    assert len([el for el in plan.elements if el.id.startswith("conclusion_")]) == 3
    assert plan.elements_by_role(LayoutElementRole.SOURCE)
    assert not report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / "v4_analytical_diagram",
        plan=plan,
        report=report,
        design=design,
        title=slide.title,
    )


def test_v5_process_narrative(intent_service: VisualIntentService) -> None:
    """V5：4 个阶段 + 箭头 + 每阶段图示 + 总结."""
    stage_assets = [uuid4() for _ in range(4)]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="phasing",
        order=5,
        title="改扩建四阶段实施路径",
        message="分期实施可在不停诊条件下完成核心区更新。",
        key_points=["现状梳理", "临时分流", "主体改造", "运营回迁"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.TIMELINE,
                description=f"阶段{i + 1}",
                preferred_asset_ids=[stage_assets[i]],
            )
            for i in range(4)
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="实施计划.pdf", page_number=2)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    intent.dominant_content_type = VisualContentType.PROCESS
    intent.preferred_layout_families = [LayoutFamily.PROCESS_NARRATIVE]
    intent.supporting_asset_ids = list(stage_assets)

    design = default_presentation_design_system()
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=list(slide.key_points),
        source_text="实施计划.pdf p.2",
        supporting_asset_refs=[str(asset_id) for asset_id in stage_assets],
        insight="四阶段闭环后恢复完整急诊效能。",
    )
    plan = LayoutSolver().generate(
        LayoutFamily.PROCESS_NARRATIVE,
        _context(
            slide=slide,
            intent=intent,
            design=design,
            variant="steps_horizontal",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)

    assert plan.layout_family == LayoutFamily.PROCESS_NARRATIVE
    assert len([el for el in plan.elements if el.id.startswith("step_")]) == 4
    assert len([el for el in plan.elements if el.id.startswith("stage_visual_")]) == 4
    assert len([el for el in plan.elements if el.id.startswith("arrow_")]) == 3
    assert plan.element_by_id("summary") is not None
    assert not report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / "v5_process_narrative",
        plan=plan,
        report=report,
        design=design,
        title=slide.title,
    )


def test_v6_metric_dashboard(intent_service: VisualIntentService) -> None:
    """V6：5 个核心指标 + 一张趋势图 + 一条结论."""
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="metrics",
        order=6,
        title="急诊核心运营指标看板",
        message="候诊压力仍是当前最需优先治理的指标。",
        key_points=[
            "日均急诊 860人",
            "平均候诊 42分钟",
            "床位周转 1.8次",
            "抢救成功率 96%",
            "满意度 78%",
        ],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.CHART,
                description="候诊趋势图",
                preferred_asset_ids=[uuid4()],
            )
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="运营数据月报.pdf", page_number=1)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    intent.dominant_content_type = VisualContentType.METRICS
    intent.preferred_layout_families = [LayoutFamily.METRIC_DASHBOARD]

    design = default_presentation_design_system()
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=[],
        metrics=list(slide.key_points),
        source_text="运营数据月报.pdf p.1",
        insight="近三月平均候诊时长持续高于目标阈值。",
    )
    plan = LayoutSolver().generate(
        LayoutFamily.METRIC_DASHBOARD,
        _context(
            slide=slide,
            intent=intent,
            design=design,
            variant="metric_with_chart",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)

    assert plan.layout_family == LayoutFamily.METRIC_DASHBOARD
    assert len(plan.elements_by_role(LayoutElementRole.METRIC)) == 5
    assert plan.element_by_id("chart") is not None
    assert plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert not report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / "v6_metric_dashboard",
        plan=plan,
        report=report,
        design=design,
        title=slide.title,
    )


def test_v7_hybrid_canvas(intent_service: VisualIntentService) -> None:
    """V7：主图纸 + 两张辅助图 + 指标 + 文字 + 图注."""
    hero_id = uuid4()
    support_ids = [uuid4(), uuid4()]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="hybrid",
        order=7,
        title="核心区改造：图纸与证据对照",
        message="主图纸给出结构骨架，辅助图与指标共同说明改造优先级。",
        key_points=["优先打通北侧急救轴", "保留南侧景观缓冲", "建筑密度 1.6", "绿地率 35%"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PLAN,
                description="核心区总图",
                preferred_asset_ids=[hero_id],
            ),
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="北侧现状",
                preferred_asset_ids=[support_ids[0]],
            ),
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="南侧现状",
                preferred_asset_ids=[support_ids[1]],
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="改造专项.pdf", page_number=9)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    intent.dominant_content_type = VisualContentType.MIXED
    intent.preferred_layout_families = [LayoutFamily.HYBRID_CANVAS]
    intent.hero_asset_id = hero_id
    intent.supporting_asset_ids = list(support_ids)

    design = default_presentation_design_system()
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=["优先打通北侧急救轴", "保留南侧景观缓冲"],
        metrics=["建筑密度 1.6", "绿地率 35%"],
        captions=["图1 核心区总平面", "图2 南北侧现状对照"],
        source_text="改造专项.pdf p.9",
        hero_asset_ref=str(hero_id),
        supporting_asset_refs=[str(asset_id) for asset_id in support_ids],
    )
    plan = LayoutSolver().generate(
        LayoutFamily.HYBRID_CANVAS,
        _context(
            slide=slide,
            intent=intent,
            design=design,
            variant="freeform",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(
        plan, design, require_source=True, drawing_hero=True
    )

    assert plan.layout_family == LayoutFamily.HYBRID_CANVAS
    hero = plan.element_by_id("hero")
    assert hero is not None
    assert hero.fit_mode == ImageFit.CONTAIN
    assert hero.crop_policy == CropPolicy.FORBIDDEN
    assert len(plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)) == 2
    assert len(plan.elements_by_role(LayoutElementRole.METRIC)) >= 1
    assert plan.elements_by_role(LayoutElementRole.CAPTION)
    assert plan.elements_by_role(LayoutElementRole.BODY_TEXT) or plan.elements_by_role(
        LayoutElementRole.LEAD_STATEMENT
    )
    assert not report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / "v7_hybrid_canvas",
        plan=plan,
        report=report,
        design=design,
        title=slide.title,
    )


def test_update_env_documented() -> None:
    """Keep the update env name discoverable for operators."""
    assert UPDATE_ENV == "UPDATE_VISUAL_COMPOSITION_GOLDENS"
