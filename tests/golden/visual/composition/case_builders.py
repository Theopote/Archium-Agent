"""Deterministic builders for visual composition golden cases V1–V9."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

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
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.generators.base import (
    LayoutContentBundle,
    LayoutGeneratorContext,
    content_from_slide,
)
from archium.infrastructure.layout.layout_solver import LayoutSolver

DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")


@dataclass(frozen=True)
class CompositionCaseResult:
    """Resolved slide, plan, and validation for one composition golden case."""

    case_id: str
    slide: SlideSpec
    intent: VisualIntent
    design: DesignSystem
    plan: LayoutPlan
    report: LayoutValidationReport

    @property
    def title(self) -> str:
        return self.slide.title


def _context(
    *,
    slide: SlideSpec,
    intent: VisualIntent,
    design: DesignSystem,
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


def build_v1_drawing_focus(intent_service: VisualIntentService) -> CompositionCaseResult:
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
    design = default_presentation_design_system()
    plan = LayoutSolver().generate(
        LayoutFamily.DRAWING_FOCUS,
        _context(slide=slide, intent=intent, design=design, variant="drawing_with_metrics"),
    )
    report = LayoutValidationService().validate(
        plan, design, require_source=True, drawing_hero=True
    )
    return CompositionCaseResult(
        case_id="v1_drawing_focus",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v2_evidence_board(intent_service: VisualIntentService) -> CompositionCaseResult:
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
    design = default_presentation_design_system()
    plan = LayoutSolver().generate(
        LayoutFamily.EVIDENCE_BOARD,
        _context(slide=slide, intent=intent, design=design, variant="numbered_grid"),
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)
    return CompositionCaseResult(
        case_id="v2_evidence_board",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v3_comparative_matrix(intent_service: VisualIntentService) -> CompositionCaseResult:
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
    return CompositionCaseResult(
        case_id="v3_comparative_matrix",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v4_analytical_diagram(intent_service: VisualIntentService) -> CompositionCaseResult:
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
    return CompositionCaseResult(
        case_id="v4_analytical_diagram",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v5_process_narrative(intent_service: VisualIntentService) -> CompositionCaseResult:
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
    return CompositionCaseResult(
        case_id="v5_process_narrative",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v6_metric_dashboard(intent_service: VisualIntentService) -> CompositionCaseResult:
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
    return CompositionCaseResult(
        case_id="v6_metric_dashboard",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v7_hybrid_canvas(intent_service: VisualIntentService) -> CompositionCaseResult:
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
    return CompositionCaseResult(
        case_id="v7_hybrid_canvas",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v8_process_narrative_icons(intent_service: VisualIntentService) -> CompositionCaseResult:
    stage_assets = [uuid4() for _ in range(4)]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="phasing-icons",
        order=8,
        title="门诊更新四阶段路径与关键动作",
        message="阶段切换需要明确的动作锚点与空间提示，降低理解成本。",
        key_points=["现状梳理", "动线分流", "分区施工", "恢复运营"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.TIMELINE,
                description=f"阶段{i + 1}",
                preferred_asset_ids=[stage_assets[i]],
            )
            for i in range(4)
        ]
        + [
            VisualRequirement(
                type=VisualType.ICON,
                description="步行流线",
                icon_canonical_name="pedestrian_flow",
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="公共交通换乘",
                icon_canonical_name="public_transport",
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="停车组织",
                icon_canonical_name="parking",
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="实施计划.pdf", page_number=4)
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
        source_text="实施计划.pdf p.4",
        supporting_asset_refs=[str(asset_id) for asset_id in stage_assets],
        icon_refs=["icon:pedestrian_flow", "icon:public_transport", "icon:parking"],
        insight="阶段之间用语义图标强化读者对转换动作的识别。",
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
    return CompositionCaseResult(
        case_id="v8_process_narrative_icons",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v9_metric_dashboard_icons(intent_service: VisualIntentService) -> CompositionCaseResult:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="metrics-icons",
        order=9,
        title="门急诊体验指标与导视能力看板",
        message="关键指标需要语义锚点，帮助读者快速识别不同维度。",
        key_points=[
            "日均到诊 860人",
            "步行可达 6分钟",
            "无障碍覆盖 92%",
            "停车周转 1.4次",
        ],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.CHART,
                description="趋势图",
                preferred_asset_ids=[uuid4()],
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="步行流线",
                icon_canonical_name="pedestrian_flow",
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="无障碍",
                icon_canonical_name="accessibility",
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="停车",
                icon_canonical_name="parking",
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="节能",
                icon_canonical_name="energy_saving",
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="运营数据月报.pdf", page_number=2)
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
        source_text="运营数据月报.pdf p.2",
        icon_refs=[
            "icon:pedestrian_flow",
            "icon:accessibility",
            "icon:parking",
            "icon:energy_saving",
        ],
        insight="图标帮助区分人流、可达性、停车与能效四类指标。",
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
    return CompositionCaseResult(
        case_id="v9_metric_dashboard_icons",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


COMPOSITION_CASE_BUILDERS: dict[str, object] = {
    "v1_drawing_focus": build_v1_drawing_focus,
    "v2_evidence_board": build_v2_evidence_board,
    "v3_comparative_matrix": build_v3_comparative_matrix,
    "v4_analytical_diagram": build_v4_analytical_diagram,
    "v5_process_narrative": build_v5_process_narrative,
    "v6_metric_dashboard": build_v6_metric_dashboard,
    "v7_hybrid_canvas": build_v7_hybrid_canvas,
}

ICON_CASE_BUILDERS: dict[str, object] = {
    "v8_process_narrative_icons": build_v8_process_narrative_icons,
    "v9_metric_dashboard_icons": build_v9_metric_dashboard_icons,
}

ICON_CASE_IDS: tuple[str, ...] = tuple(ICON_CASE_BUILDERS.keys())
COMPOSITION_CASE_IDS: tuple[str, ...] = tuple(COMPOSITION_CASE_BUILDERS.keys())

# Calibrated single-slide layouts used for PPTX screenshot regression.
SCREENSHOT_CASE_IDS: tuple[str, ...] = (*COMPOSITION_CASE_IDS, *ICON_CASE_IDS)


def build_composition_case(case_id: str, intent_service: VisualIntentService) -> CompositionCaseResult:
    builder = COMPOSITION_CASE_BUILDERS.get(case_id) or ICON_CASE_BUILDERS.get(case_id)
    if builder is None:
        msg = f"Unknown composition case: {case_id}"
        raise ValueError(msg)
    return builder(intent_service)  # type: ignore[operator,no-any-return]
