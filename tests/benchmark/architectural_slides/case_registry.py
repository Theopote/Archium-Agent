"""Registry of architectural slide benchmark cases."""

from __future__ import annotations

from uuid import UUID

from archium.application.visual.benchmark_service import (
    BenchmarkCaseBuildRequest,
    BenchmarkSlideContent,
)
from archium.domain.enums import VisualType
from archium.domain.slide import VisualRequirement
from archium.domain.visual.benchmark import ArchitecturalSlideCategory, BenchmarkCaseDefinition
from archium.domain.visual.enums import LayoutFamily, VisualContentType

# Stable asset IDs for deterministic baselines.
CASE_001_HERO = UUID("c0010001-0001-4001-8001-000000000001")
CASE_002_PHOTOS = (
    UUID("c0020001-0001-4001-8001-000000000001"),
    UUID("c0020002-0001-4001-8001-000000000002"),
    UUID("c0020003-0001-4001-8001-000000000003"),
    UUID("c0020004-0001-4001-8001-000000000004"),
)
CASE_003_IMAGES = (
    UUID("c0030001-0001-4001-8001-000000000001"),
    UUID("c0030002-0001-4001-8001-000000000002"),
    UUID("c0030003-0001-4001-8001-000000000003"),
)
CASE_004_CHART = UUID("c0040001-0001-4001-8001-000000000001")

BENCHMARK_CASE_DEFINITIONS: tuple[BenchmarkCaseDefinition, ...] = (
    BenchmarkCaseDefinition(
        case_id="case_001_site_plan",
        title="院区总平面与指标",
        category=ArchitecturalSlideCategory.DRAWING,
        page_type="单张总平面主导页",
        page_task="以总平面为主视觉，辅以关键规划指标说明改造范围。",
        visual_focus="总平面图纸应占据页面主视觉区，指标作为辅助阅读。",
        expected_layout_family=LayoutFamily.DRAWING_FOCUS,
        allowed_layout_variants=("drawing_with_metrics", "drawing_only"),
        layout_variant="drawing_with_metrics",
        chapter_id="site_plan",
        slide_order=1,
    ),
    BenchmarkCaseDefinition(
        case_id="case_002_site_photos",
        title="老院区交通与环境问题",
        category=ArchitecturalSlideCategory.PHOTO_ANALYSIS,
        page_type="四张现场问题照片",
        page_task="用四张现场照片并列呈现交通混乱与环境短板。",
        visual_focus="四张照片等权重排列，标题点明问题主题。",
        expected_layout_family=LayoutFamily.EVIDENCE_BOARD,
        allowed_layout_variants=("numbered_grid", "caption_grid"),
        layout_variant="numbered_grid",
        chapter_id="site_issues",
        slide_order=2,
    ),
    BenchmarkCaseDefinition(
        case_id="case_003_case_comparison",
        title="国内外三座医疗更新案例比较",
        category=ArchitecturalSlideCategory.CASE_COMPARISON,
        page_type="三案例横向比较",
        page_task="横向比较三个案例的空间策略与公众可达性。",
        visual_focus="三案例图像尺度一致，结论区收束比较洞察。",
        expected_layout_family=LayoutFamily.COMPARATIVE_MATRIX,
        allowed_layout_variants=("matrix_with_insight", "matrix_only"),
        layout_variant="matrix_with_insight",
        chapter_id="reference_cases",
        slide_order=3,
    ),
    BenchmarkCaseDefinition(
        case_id="case_004_economic_metrics",
        title="经济技术指标一览",
        category=ArchitecturalSlideCategory.DATA_METRICS,
        page_type="经济技术指标",
        page_task="汇总用地、建筑面积与关键经济技术指标。",
        visual_focus="指标卡片清晰可读，趋势图辅助解释关键变化。",
        expected_layout_family=LayoutFamily.METRIC_DASHBOARD,
        allowed_layout_variants=("metric_with_chart", "metrics_only"),
        layout_variant="metric_with_chart",
        chapter_id="metrics",
        slide_order=4,
    ),
    BenchmarkCaseDefinition(
        case_id="case_005_design_concept",
        title="设计理念：以患者路径组织空间",
        category=ArchitecturalSlideCategory.TEXT_NARRATIVE,
        page_type="设计理念",
        page_task="阐述以患者路径为主线的空间组织理念。",
        visual_focus="核心论断突出，正文层次清晰，留白适度。",
        expected_layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        allowed_layout_variants=("lead_and_points", "two_column_text", "quote_argument"),
        layout_variant="lead_and_points",
        chapter_id="concept",
        slide_order=5,
    ),
)

BENCHMARK_CASE_IDS: tuple[str, ...] = tuple(item.case_id for item in BENCHMARK_CASE_DEFINITIONS)

_DEFINITION_BY_ID: dict[str, BenchmarkCaseDefinition] = {
    item.case_id: item for item in BENCHMARK_CASE_DEFINITIONS
}


def get_case_definition(case_id: str) -> BenchmarkCaseDefinition:
    definition = _DEFINITION_BY_ID.get(case_id)
    if definition is None:
        msg = f"Unknown architectural benchmark case: {case_id}"
        raise ValueError(msg)
    return definition


def build_case_request(case_id: str) -> BenchmarkCaseBuildRequest:
    """Return build request for a registered benchmark case."""
    definition = get_case_definition(case_id)
    if case_id == "case_001_site_plan":
        return BenchmarkCaseBuildRequest(
            definition=definition,
            design_system=_default_design(),
            title="院区总平面与改造范围",
            message="总平面明确急救、门诊与后勤分区，并标注近期改造范围。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="院区总平面图",
                    preferred_asset_ids=[CASE_001_HERO],
                )
            ],
            content=BenchmarkSlideContent(
                key_points=["绿地率 38%", "容积率 1.6", "改造范围 2.4ha", "急救独立入口"],
                drawing_hero=True,
                hero_asset_id=CASE_001_HERO,
            ),
            source_document="院区总体规划.pdf",
            source_page=4,
        )
    if case_id == "case_002_site_photos":
        return BenchmarkCaseBuildRequest(
            definition=definition,
            design_system=_default_design(),
            title="老院区交通与环境问题",
            message="入口混行、停车占道与景观缺失叠加，患者到达体验差。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PHOTO,
                    description=f"现场问题照片 {index + 1}",
                    preferred_asset_ids=[CASE_002_PHOTOS[index]],
                )
                for index in range(4)
            ],
            content=BenchmarkSlideContent(
                key_points=["入口混行", "停车占道", "景观缺失", "导向不清"],
                supporting_asset_ids=list(CASE_002_PHOTOS),
                dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
                preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
            ),
            source_document="现场踏勘记录.pdf",
            source_page=6,
        )
    if case_id == "case_003_case_comparison":
        return BenchmarkCaseBuildRequest(
            definition=definition,
            design_system=_default_design(),
            title="三座医疗更新案例横向比较",
            message="三个案例均通过公共界面与流线重组提升可达性，而非单纯扩容。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.COMPARISON,
                    description="案例比较",
                    preferred_asset_ids=[CASE_003_IMAGES[0]],
                ),
                VisualRequirement(
                    type=VisualType.REFERENCE_CASE,
                    description="案例 B",
                    preferred_asset_ids=[CASE_003_IMAGES[1]],
                ),
                VisualRequirement(
                    type=VisualType.REFERENCE_CASE,
                    description="案例 C",
                    preferred_asset_ids=[CASE_003_IMAGES[2]],
                ),
            ],
            content=BenchmarkSlideContent(
                key_points=["空间策略", "运营模式", "公众可达性", "改造强度"],
                insight="应优先重建公共性与可达性，而非单纯增加面积。",
                dominant_content_type=VisualContentType.COMPARISON,
                preferred_layout_families=[LayoutFamily.COMPARATIVE_MATRIX],
            ),
            source_document="案例研究汇编.pdf",
            source_page=12,
        )
    if case_id == "case_004_economic_metrics":
        return BenchmarkCaseBuildRequest(
            definition=definition,
            design_system=_default_design(),
            title="经济技术指标",
            message="改造后总建筑面积控制在合理区间，公服与绿地指标同步提升。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.CHART,
                    description="指标趋势图",
                    preferred_asset_ids=[CASE_004_CHART],
                )
            ],
            content=BenchmarkSlideContent(
                metrics=[
                    "用地面积 3.2ha",
                    "总建筑面积 4.8万㎡",
                    "容积率 1.5",
                    "绿地率 35%",
                    "停车位 420个",
                ],
                insight="公服与绿地指标同步提升，容积率控制在规划上限以内。",
                dominant_content_type=VisualContentType.METRICS,
                preferred_layout_families=[LayoutFamily.METRIC_DASHBOARD],
            ),
            source_document="可研报告.pdf",
            source_page=18,
        )
    if case_id == "case_005_design_concept":
        return BenchmarkCaseBuildRequest(
            definition=definition,
            design_system=_default_design(),
            title="设计理念：以患者路径组织空间",
            message="设计以患者路径为主线，将到达、候诊、诊疗与离院串联为清晰空间序列。",
            visual_requirements=[],
            content=BenchmarkSlideContent(
                key_points=[
                    "到达层分离急救与门诊",
                    "候诊区面向内院开放",
                    "诊疗区按科室成组",
                    "离院路径避免交叉",
                ],
                dominant_content_type=VisualContentType.TEXT_ARGUMENT,
                preferred_layout_families=[LayoutFamily.TEXTUAL_ARGUMENT],
            ),
            source_document="方案说明书.pdf",
            source_page=3,
        )
    msg = f"No build request configured for case: {case_id}"
    raise ValueError(msg)


def _default_design():
    from archium.domain.visual import default_presentation_design_system

    return default_presentation_design_system()
