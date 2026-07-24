"""Deterministic builders for visual composition golden cases V1–V9."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_grammar_intent import preferred_variant_for_intent
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.domain.citation import Citation
from archium.domain.enums import SlideType, VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual import (
    LayoutFamily,
    VisualContentType,
    default_presentation_design_system,
)
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
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

# Stable asset UUIDs for archetype golden cases V19–V23.
ARCHETYPE_MAP_ASSET = UUID("a0190001-0001-4001-8001-000000000001")
ARCHETYPE_PHOTO_ASSETS = (
    UUID("a0200001-0001-4001-8001-000000000001"),
    UUID("a0200002-0001-4001-8001-000000000002"),
)
ARCHETYPE_CONCEPT_ASSET = UUID("a0210001-0001-4001-8001-000000000001")
ARCHETYPE_BEFORE_ASSET = UUID("a0220001-0001-4001-8001-000000000001")
ARCHETYPE_AFTER_ASSET = UUID("a0220002-0001-4001-8001-000000000002")
ARCHETYPE_OPENING_PHOTO = UUID("a0230001-0001-4001-8001-000000000001")


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


def _dark_design() -> DesignSystem:
    design = default_presentation_design_system().model_copy(deep=True)
    design.colors.background = "#1A1A1A"
    design.colors.surface = "#2A2A2A"
    design.colors.primary_text = "#F5F5F5"
    design.colors.secondary_text = "#CCCCCC"
    design.colors.muted_text = "#999999"
    design.colors.primary = "#6BA3D0"
    design.colors.accent = "#E8A87C"
    design.colors.border = "#444444"
    design.name = "Dark Presentation"
    return design


def _light_design() -> DesignSystem:
    design = default_presentation_design_system().model_copy(deep=True)
    design.colors.background = "#FFFFFF"
    design.colors.surface = "#F8F8F8"
    design.colors.primary_text = "#111111"
    design.colors.accent = "#C45C26"
    design.name = "Light Presentation"
    return design


def _page_4x3(design: DesignSystem) -> DesignSystem:
    updated = design.model_copy(deep=True)
    updated.page = updated.page.model_copy(
        update={"width": 10.0, "height": 7.5}
    )
    return updated


def build_v10_icons_long_cjk_title(intent_service: VisualIntentService) -> CompositionCaseResult:
    """Icons + very long Chinese title (wrapping / hierarchy stress)."""
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="icons-long-title",
        order=10,
        title="既有医院门急诊综合体更新实施中关于步行流线重组、无障碍覆盖与停车周转协同的阶段性关键指标解读",
        message="长标题下图标仍需可读，不得挤压结论区。",
        key_points=["日均到诊 860人", "步行可达 6分钟", "无障碍覆盖 92%"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.ICON,
                description="步行",
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
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="指标说明.pdf", page_number=1)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    intent.dominant_content_type = VisualContentType.METRICS
    intent.preferred_layout_families = [LayoutFamily.METRIC_DASHBOARD]
    design = default_presentation_design_system()
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        metrics=list(slide.key_points),
        source_text="指标说明.pdf p.1",
        icon_refs=["icon:pedestrian_flow", "icon:accessibility", "icon:parking"],
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
        case_id="v10_icons_long_cjk_title",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v11_icons_dark_theme(intent_service: VisualIntentService) -> CompositionCaseResult:
    base = build_v9_metric_dashboard_icons(intent_service)
    design = _dark_design()
    content = LayoutContentBundle(
        title=base.slide.title,
        message=base.slide.message,
        metrics=list(base.slide.key_points),
        source_text="运营数据月报.pdf p.2",
        icon_refs=[
            "icon:pedestrian_flow",
            "icon:accessibility",
            "icon:parking",
            "icon:energy_saving",
        ],
    )
    plan = LayoutSolver().generate(
        LayoutFamily.METRIC_DASHBOARD,
        _context(
            slide=base.slide,
            intent=base.intent,
            design=design,
            variant="metric_with_chart",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)
    return CompositionCaseResult(
        case_id="v11_icons_dark_theme",
        slide=base.slide,
        intent=base.intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v12_icons_light_theme(intent_service: VisualIntentService) -> CompositionCaseResult:
    base = build_v9_metric_dashboard_icons(intent_service)
    design = _light_design()
    content = LayoutContentBundle(
        title=base.slide.title,
        message=base.slide.message,
        metrics=list(base.slide.key_points),
        source_text="运营数据月报.pdf p.2",
        icon_refs=[
            "icon:pedestrian_flow",
            "icon:accessibility",
            "icon:parking",
            "icon:energy_saving",
        ],
    )
    plan = LayoutSolver().generate(
        LayoutFamily.METRIC_DASHBOARD,
        _context(
            slide=base.slide,
            intent=base.intent,
            design=design,
            variant="metric_with_chart",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)
    return CompositionCaseResult(
        case_id="v12_icons_light_theme",
        slide=base.slide,
        intent=base.intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v13_icons_small_size(intent_service: VisualIntentService) -> CompositionCaseResult:
    """Metric icons forced to a small decorative band (size stress)."""
    base = build_v9_metric_dashboard_icons(intent_service)
    plan = base.plan.model_copy(deep=True)
    for element in plan.elements:
        if (
            element.role == LayoutElementRole.DECORATION
            and element.content_type == LayoutContentType.IMAGE
            and str(element.content_ref or "").startswith("icon:")
        ):
            element.width = 0.18
            element.height = 0.16
    return CompositionCaseResult(
        case_id="v13_icons_small_size",
        slide=base.slide,
        intent=base.intent,
        design=base.design,
        plan=plan,
        report=base.report,
    )


def build_v14_icons_stroke_recolor(
    intent_service: VisualIntentService,
) -> CompositionCaseResult:
    """Accent theme recolor — icon SVG strokes map to ``design.colors.accent``."""
    base = build_v9_metric_dashboard_icons(intent_service)
    design = base.design.model_copy(deep=True)
    design.colors.accent = "#E63946"
    design.colors.primary = "#E63946"
    return CompositionCaseResult(
        case_id="v14_icons_stroke_recolor",
        slide=base.slide,
        intent=base.intent,
        design=design,
        plan=base.plan,
        report=base.report,
    )


def build_v15_icons_aspect_4x3(intent_service: VisualIntentService) -> CompositionCaseResult:
    base = build_v8_process_narrative_icons(intent_service)
    design = _page_4x3(base.design)
    content = LayoutContentBundle(
        title=base.slide.title,
        message=base.slide.message,
        key_points=list(base.slide.key_points),
        source_text="实施计划.pdf p.4",
        supporting_asset_refs=list(
            str(asset_id) for asset_id in base.intent.supporting_asset_ids
        ),
        icon_refs=["icon:pedestrian_flow", "icon:public_transport", "icon:parking"],
    )
    plan = LayoutSolver().generate(
        LayoutFamily.PROCESS_NARRATIVE,
        _context(
            slide=base.slide,
            intent=base.intent,
            design=design,
            variant="steps_horizontal",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)
    return CompositionCaseResult(
        case_id="v15_icons_aspect_4x3",
        slide=base.slide,
        intent=base.intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v16_icons_missing_fallback(intent_service: VisualIntentService) -> CompositionCaseResult:
    """Known-bad semantic name — asset resolve must not invent a path."""
    base = build_v8_process_narrative_icons(intent_service)
    content = LayoutContentBundle(
        title=base.slide.title,
        message=base.slide.message,
        key_points=list(base.slide.key_points),
        source_text="实施计划.pdf p.4",
        supporting_asset_refs=list(
            str(asset_id) for asset_id in base.intent.supporting_asset_ids
        ),
        icon_refs=["icon:does_not_exist_in_registry"],
    )
    plan = LayoutSolver().generate(
        LayoutFamily.PROCESS_NARRATIVE,
        _context(
            slide=base.slide,
            intent=base.intent,
            design=base.design,
            variant="steps_horizontal",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(plan, base.design, require_source=True)
    return CompositionCaseResult(
        case_id="v16_icons_missing_fallback",
        slide=base.slide,
        intent=base.intent,
        design=base.design,
        plan=plan,
        report=report,
    )


def build_v17_icons_illegal_ref(intent_service: VisualIntentService) -> CompositionCaseResult:
    """Malformed icon refs must not crash layout or export adapters."""
    base = build_v9_metric_dashboard_icons(intent_service)
    content = LayoutContentBundle(
        title=base.slide.title,
        message=base.slide.message,
        metrics=list(base.slide.key_points),
        source_text="运营数据月报.pdf p.2",
        icon_refs=["icon:", "icon:/../etc/passwd", "not-an-icon-ref"],
    )
    plan = LayoutSolver().generate(
        LayoutFamily.METRIC_DASHBOARD,
        _context(
            slide=base.slide,
            intent=base.intent,
            design=base.design,
            variant="metric_with_chart",
            content=content,
        ),
    )
    report = LayoutValidationService().validate(plan, base.design, require_source=True)
    return CompositionCaseResult(
        case_id="v17_icons_illegal_ref",
        slide=base.slide,
        intent=base.intent,
        design=base.design,
        plan=plan,
        report=report,
    )


def build_v18_icons_dense_eight_steps(intent_service: VisualIntentService) -> CompositionCaseResult:
    """Eight process steps — dense page with many icon arrows (policy may clamp)."""
    stage_assets = [uuid4() for _ in range(8)]
    steps = [f"阶段{i + 1}动作" for i in range(8)]
    # Bypass editorial max key_points=5 — this case intentionally stress-tests density.
    slide = SlideSpec.model_construct(
        id=uuid4(),
        presentation_id=uuid4(),
        lineage_id=uuid4(),
        logical_key="dense-icons-p18",
        chapter_id="dense-icons",
        order=18,
        title="八步实施路径与关键动作",
        message="密集流程页用于验证图标密度策略与箭头占位。",
        slide_type="content",
        layout_id="default",
        key_points=steps,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.TIMELINE,
                description=f"阶段{i + 1}",
                preferred_asset_ids=[stage_assets[i]],
            )
            for i in range(8)
        ]
        + [
            VisualRequirement(
                type=VisualType.ICON,
                description=name,
                icon_canonical_name=name,
            )
            for name in (
                "pedestrian_flow",
                "public_transport",
                "parking",
                "accessibility",
                "energy_saving",
                "healthcare",
                "education",
                "smart_systems",
            )
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="实施计划.pdf", page_number=8)
        ],
        version=1,
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    intent.dominant_content_type = VisualContentType.PROCESS
    intent.preferred_layout_families = [LayoutFamily.PROCESS_NARRATIVE]
    intent.supporting_asset_ids = list(stage_assets)
    design = default_presentation_design_system()
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=steps,
        source_text="实施计划.pdf p.8",
        supporting_asset_refs=[str(asset_id) for asset_id in stage_assets],
        icon_refs=[
            "icon:pedestrian_flow",
            "icon:public_transport",
            "icon:parking",
            "icon:accessibility",
            "icon:energy_saving",
            "icon:healthcare",
            "icon:education",
            "icon:smart_systems",
        ],
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
        case_id="v18_icons_dense_eight_steps",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def _generate_archetype_plan(
    *,
    slide: SlideSpec,
    intent: VisualIntent,
    family: LayoutFamily,
    design: DesignSystem,
    fallback_variant: str,
) -> LayoutPlan:
    variant = preferred_variant_for_intent(intent, family) or fallback_variant
    return LayoutSolver().generate(
        family,
        _context(slide=slide, intent=intent, design=design, variant=variant),
    )


def build_v23_narrative_opening(
    intent_service: VisualIntentService,
) -> CompositionCaseResult:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="opening",
        order=0,
        title="老院区更新汇报开篇",
        message="历史院区面临流线交叉与空间矛盾，更新目标是可持续运营。",
        key_points=["流线交叉拥堵", "后勤空间老化", "可持续运营"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="历史院区照片",
                preferred_asset_ids=[ARCHETYPE_OPENING_PHOTO],
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="院史资料.pdf", page_number=1),
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    design = default_presentation_design_system()
    plan = _generate_archetype_plan(
        slide=slide,
        intent=intent,
        family=LayoutFamily.HYBRID_CANVAS,
        design=design,
        fallback_variant="narrative_opening",
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)
    return CompositionCaseResult(
        case_id="v23_narrative_opening",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v19_site_context_analysis(
    intent_service: VisualIntentService,
) -> CompositionCaseResult:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="context",
        order=1,
        title="区位与交通分析",
        message="基地位于轨道站点 800m 辐射圈，主干道可达性良好。",
        key_points=["地铁 800m", "主干道贯通", "服务半径 500m"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.MAP,
                description="区位地图",
                preferred_asset_ids=[ARCHETYPE_MAP_ASSET],
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="区位分析.pdf", page_number=2),
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    design = default_presentation_design_system()
    plan = _generate_archetype_plan(
        slide=slide,
        intent=intent,
        family=LayoutFamily.HYBRID_CANVAS,
        design=design,
        fallback_variant="site_context",
    )
    report = LayoutValidationService().validate(plan, design, require_source=True, drawing_hero=True)
    return CompositionCaseResult(
        case_id="v19_site_context_analysis",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v20_site_problem_diagnosis(
    intent_service: VisualIntentService,
) -> CompositionCaseResult:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="problem",
        order=2,
        title="现状问题诊断",
        message="结构老化与空间不足并存，需优先解决安全与流线问题。",
        key_points=["结构老化", "空间不足", "流线混乱"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="现场照片1",
                preferred_asset_ids=[ARCHETYPE_PHOTO_ASSETS[0]],
            ),
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="现场照片2",
                preferred_asset_ids=[ARCHETYPE_PHOTO_ASSETS[1]],
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="现场踏勘.pdf", page_number=5),
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    design = default_presentation_design_system()
    plan = _generate_archetype_plan(
        slide=slide,
        intent=intent,
        family=LayoutFamily.EVIDENCE_BOARD,
        design=design,
        fallback_variant="diagnosis_split",
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)
    return CompositionCaseResult(
        case_id="v20_site_problem_diagnosis",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v21_design_strategy(intent_service: VisualIntentService) -> CompositionCaseResult:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="strategy",
        order=3,
        title="设计策略与原则",
        message="以开放院落串联历史肌理与现代功能。",
        key_points=["开放公共", "历史肌理", "现代功能", "空间渗透", "慢行系统"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.DIAGRAM,
                description="概念示意",
                preferred_asset_ids=[ARCHETYPE_CONCEPT_ASSET],
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="设计说明.pdf", page_number=8),
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    design = default_presentation_design_system()
    plan = _generate_archetype_plan(
        slide=slide,
        intent=intent,
        family=LayoutFamily.STRATEGY_CARDS,
        design=design,
        fallback_variant="strategy_concept",
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)
    return CompositionCaseResult(
        case_id="v21_design_strategy",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


def build_v22_before_after_transformation(
    intent_service: VisualIntentService,
) -> CompositionCaseResult:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="transform",
        order=4,
        title="改造前后对比",
        message="改造后公共界面与可达性显著提升。",
        slide_type=SlideType.COMPARISON,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="改造前",
                preferred_asset_ids=[ARCHETYPE_BEFORE_ASSET],
            ),
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="改造后",
                preferred_asset_ids=[ARCHETYPE_AFTER_ASSET],
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="改造记录.pdf", page_number=3),
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    design = default_presentation_design_system()
    plan = _generate_archetype_plan(
        slide=slide,
        intent=intent,
        family=LayoutFamily.COMPARATIVE_MATRIX,
        design=design,
        fallback_variant="before_after",
    )
    report = LayoutValidationService().validate(plan, design, require_source=True)
    return CompositionCaseResult(
        case_id="v22_before_after_transformation",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=report,
    )


# Visual Grammar archetype cases — JSON/preview baselines (builders + unit tests first).
ARCHETYPE_CASE_BUILDERS: dict[str, object] = {
    "v19_site_context_analysis": build_v19_site_context_analysis,
    "v20_site_problem_diagnosis": build_v20_site_problem_diagnosis,
    "v21_design_strategy": build_v21_design_strategy,
    "v22_before_after_transformation": build_v22_before_after_transformation,
    "v23_narrative_opening": build_v23_narrative_opening,
}

ARCHETYPE_CASE_IDS: tuple[str, ...] = tuple(ARCHETYPE_CASE_BUILDERS.keys())

COMPOSITION_CASE_BUILDERS: dict[str, object] = {
    "v1_drawing_focus": build_v1_drawing_focus,
    "v2_evidence_board": build_v2_evidence_board,
    "v3_comparative_matrix": build_v3_comparative_matrix,
    "v4_analytical_diagram": build_v4_analytical_diagram,
    "v5_process_narrative": build_v5_process_narrative,
    "v6_metric_dashboard": build_v6_metric_dashboard,
    "v7_hybrid_canvas": build_v7_hybrid_canvas,
}

# Icon cases with committed pptx_screenshot baselines (CI-gated).
ICON_BASELINE_CASE_BUILDERS: dict[str, object] = {
    "v8_process_narrative_icons": build_v8_process_narrative_icons,
    "v9_metric_dashboard_icons": build_v9_metric_dashboard_icons,
    "v14_icons_stroke_recolor": build_v14_icons_stroke_recolor,
}

# Expanded icon cases — builders + unit tests first; pptx baselines via approve flow.
ICON_EXPANSION_CASE_BUILDERS: dict[str, object] = {
    "v10_icons_long_cjk_title": build_v10_icons_long_cjk_title,
    "v11_icons_dark_theme": build_v11_icons_dark_theme,
    "v12_icons_light_theme": build_v12_icons_light_theme,
    "v13_icons_small_size": build_v13_icons_small_size,
    "v15_icons_aspect_4x3": build_v15_icons_aspect_4x3,
    "v16_icons_missing_fallback": build_v16_icons_missing_fallback,
    "v17_icons_illegal_ref": build_v17_icons_illegal_ref,
    "v18_icons_dense_eight_steps": build_v18_icons_dense_eight_steps,
}

ICON_CASE_BUILDERS: dict[str, object] = {
    **ICON_BASELINE_CASE_BUILDERS,
    **ICON_EXPANSION_CASE_BUILDERS,
}

ICON_CASE_IDS: tuple[str, ...] = tuple(ICON_CASE_BUILDERS.keys())
ICON_BASELINE_CASE_IDS: tuple[str, ...] = tuple(ICON_BASELINE_CASE_BUILDERS.keys())
ICON_EXPANSION_CASE_IDS: tuple[str, ...] = tuple(ICON_EXPANSION_CASE_BUILDERS.keys())
COMPOSITION_CASE_IDS: tuple[str, ...] = tuple(COMPOSITION_CASE_BUILDERS.keys())

# Cases with committed pptx_screenshot.png that CI must compare.
PPTX_VISUAL_REGRESSION_CASE_IDS: tuple[str, ...] = (
    *COMPOSITION_CASE_IDS,
    *ICON_BASELINE_CASE_IDS,
)
# Back-compat alias used by older scripts/tests.
SCREENSHOT_CASE_IDS: tuple[str, ...] = PPTX_VISUAL_REGRESSION_CASE_IDS


def build_composition_case(case_id: str, intent_service: VisualIntentService) -> CompositionCaseResult:
    builder = (
        COMPOSITION_CASE_BUILDERS.get(case_id)
        or ARCHETYPE_CASE_BUILDERS.get(case_id)
        or ICON_CASE_BUILDERS.get(case_id)
    )
    if builder is None:
        msg = f"Unknown composition case: {case_id}"
        raise ValueError(msg)
    return builder(intent_service)  # type: ignore[operator,no-any-return]
