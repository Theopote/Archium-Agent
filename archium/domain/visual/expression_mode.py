"""Architecture Expression Modes — deliverable page recipes (v0.3 Phase 2).

Not PowerPoint masters. Each mode locks layout family + variant + copy budget
+ composition bias so generators produce "建筑事务所表达" rather than generic slides.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import DensityLevel, LayoutFamily
from archium.domain.visual.page_direction import CompositionBias, CopyBudget
from archium.domain.visual.visual_grammar import PageArchetype


class ExpressionModeId(StrEnum):
    """Ten showcase expression modes (Presentation Engine v0.3 Phase 2)."""

    HERO_OPENING = "hero_opening"
    PROBLEM_TO_SOLUTION = "problem_to_solution"
    DRAWING_STORY = "drawing_story"
    BEFORE_AFTER = "before_after"
    EVIDENCE_BOARD = "evidence_board"
    ANALYTICAL_DIAGRAM = "analytical_diagram"
    STRATEGY_CARDS = "strategy_cards"
    PROCESS_NARRATIVE = "process_narrative"
    METRIC_DASHBOARD = "metric_dashboard"
    HYBRID_CLIMAX = "hybrid_climax"


class PairRole(StrEnum):
    """Role within a multi-page expression pair (e.g. Problem → Solution)."""

    NONE = "none"
    PROBLEM = "problem"
    SOLUTION = "solution"


class ExpressionMode(DomainModel):
    """One architecture expression mode — intent recipe, not coordinates."""

    id: ExpressionModeId
    display_name: str = Field(min_length=1, max_length=80)
    description: str = ""
    primary_family: LayoutFamily
    primary_variant: str = Field(min_length=1, max_length=80)
    fallback_families: tuple[LayoutFamily, ...] = ()
    forbidden_families: frozenset[LayoutFamily] = frozenset()
    composition_bias: tuple[CompositionBias, ...] = ()
    copy_budget: CopyBudget = Field(default_factory=CopyBudget)
    density: DensityLevel = DensityLevel.BALANCED
    page_archetype: PageArchetype | None = None
    pair_role: PairRole = PairRole.NONE
    must_show: tuple[str, ...] = ()
    must_hide: tuple[str, ...] = ()
    title_patterns: tuple[str, ...] = ()
    body_patterns: tuple[str, ...] = ()
    # Human "像不像建筑所" checklist (Phase 4 scoring aid).
    human_checklist: tuple[str, ...] = ()


_MODES: dict[ExpressionModeId, ExpressionMode] = {
    ExpressionModeId.HERO_OPENING: ExpressionMode(
        id=ExpressionModeId.HERO_OPENING,
        display_name="Hero Opening",
        description="大图 + 一句概念 + 极少文字。",
        primary_family=LayoutFamily.HERO,
        primary_variant="full_bleed",
        fallback_families=(LayoutFamily.HYBRID_CANVAS,),
        forbidden_families=frozenset(
            {
                LayoutFamily.METRIC_DASHBOARD,
                LayoutFamily.EVIDENCE_BOARD,
                LayoutFamily.TEXTUAL_ARGUMENT,
                LayoutFamily.STRATEGY_CARDS,
            }
        ),
        composition_bias=(CompositionBias.HERO_FULL,),
        copy_budget=CopyBudget(
            max_title_chars=24,
            max_message_chars=48,
            max_key_points=0,
            max_body_blocks=0,
        ),
        density=DensityLevel.SPACIOUS,
        page_archetype=PageArchetype.NARRATIVE_OPENING,
        must_show=("hero_image", "one_line_concept"),
        must_hide=("key_point_list", "metric_wall", "dense_caption"),
        title_patterns=(r"封面", r"开篇", r"愿景", r"概念", r"opening", r"cover"),
        body_patterns=(r"一句", r"宣言", r"愿景", r"concept"),
        human_checklist=(
            "主图是否占支配地位",
            "文字是否克制到一句概念",
            "是否像竞赛/事务所封面而非模板封面",
        ),
    ),
    ExpressionModeId.PROBLEM_TO_SOLUTION: ExpressionMode(
        id=ExpressionModeId.PROBLEM_TO_SOLUTION,
        display_name="Problem → Solution",
        description="问题照片 → 分析 → 策略条（问题页半对）。",
        primary_family=LayoutFamily.EVIDENCE_BOARD,
        primary_variant="diagnosis_split",
        fallback_families=(LayoutFamily.ANALYTICAL_DIAGRAM, LayoutFamily.STRATEGY_CARDS),
        forbidden_families=frozenset(
            {LayoutFamily.HERO, LayoutFamily.METRIC_DASHBOARD, LayoutFamily.TEXTUAL_ARGUMENT}
        ),
        composition_bias=(
            CompositionBias.EVIDENCE_GRID,
            CompositionBias.CONCLUSION_BAR,
        ),
        copy_budget=CopyBudget(
            max_title_chars=32,
            max_message_chars=80,
            max_key_points=3,
            max_body_blocks=1,
        ),
        density=DensityLevel.COMPACT,
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        pair_role=PairRole.PROBLEM,
        must_show=("problem_photos", "problem_tags", "bridge_to_strategy"),
        must_hide=("long_body_paragraphs", "unrelated_metrics"),
        title_patterns=(r"问题", r"痛点", r"矛盾", r"诊断", r"problem"),
        body_patterns=(r"因此", r"对策", r"策略回应", r"solution", r"回应"),
        human_checklist=(
            "问题是否可见（照片/标签）",
            "是否暗示向策略页过渡",
            "是否避免空泛三段论",
        ),
    ),
    ExpressionModeId.DRAWING_STORY: ExpressionMode(
        id=ExpressionModeId.DRAWING_STORY,
        display_name="Drawing Story",
        description="总平/图纸主导 + 编号 + 解释。",
        primary_family=LayoutFamily.DRAWING_FOCUS,
        primary_variant="drawing_with_annotations",
        fallback_families=(LayoutFamily.ANALYTICAL_DIAGRAM,),
        forbidden_families=frozenset(
            {LayoutFamily.HERO, LayoutFamily.METRIC_DASHBOARD, LayoutFamily.EVIDENCE_BOARD}
        ),
        composition_bias=(CompositionBias.DRAWING_DOMINANT,),
        copy_budget=CopyBudget(
            max_title_chars=30,
            max_message_chars=80,
            max_key_points=3,
            max_body_blocks=1,
        ),
        density=DensityLevel.COMPACT,
        page_archetype=PageArchetype.SITE_CONTEXT_ANALYSIS,
        must_show=("primary_drawing", "keyed_annotations", "north_or_scale"),
        must_hide=("photo_wall", "three_column_text"),
        title_patterns=(r"总平", r"总图", r"平面", r"立面", r"剖面", r"图纸"),
        body_patterns=(r"编号", r"图注", r"轴线", r"annotation"),
        human_checklist=(
            "图纸是否完整可读（contain）",
            "编号与解释是否一一对应",
            "是否像设计院图板而非插图装饰",
        ),
    ),
    ExpressionModeId.BEFORE_AFTER: ExpressionMode(
        id=ExpressionModeId.BEFORE_AFTER,
        display_name="Before / After",
        description="过去 / 未来 / 变化逻辑。",
        primary_family=LayoutFamily.COMPARATIVE_MATRIX,
        primary_variant="before_after",
        fallback_families=(LayoutFamily.HYBRID_CANVAS,),
        forbidden_families=frozenset(
            {LayoutFamily.HERO, LayoutFamily.STRATEGY_CARDS, LayoutFamily.TEXTUAL_ARGUMENT}
        ),
        composition_bias=(CompositionBias.BEFORE_AFTER,),
        copy_budget=CopyBudget(
            max_title_chars=28,
            max_message_chars=72,
            max_key_points=2,
            max_body_blocks=1,
        ),
        density=DensityLevel.BALANCED,
        page_archetype=PageArchetype.BEFORE_AFTER_TRANSFORMATION,
        must_show=("before_state", "after_state", "change_insight"),
        must_hide=("unrelated_third_column",),
        title_patterns=(r"前后", r"改造对比", r"before", r"after", r"对比"),
        body_patterns=(r"变化", r"提升", r"改善", r"transformation"),
        human_checklist=(
            "前后是否等权对照",
            "变化逻辑是否一句话可读",
            "是否避免假现场效果图冒充成果",
        ),
    ),
    ExpressionModeId.EVIDENCE_BOARD: ExpressionMode(
        id=ExpressionModeId.EVIDENCE_BOARD,
        display_name="Evidence Board",
        description="现场问题网格 + 结论条。",
        primary_family=LayoutFamily.EVIDENCE_BOARD,
        primary_variant="numbered_grid",
        fallback_families=(LayoutFamily.HYBRID_CANVAS,),
        forbidden_families=frozenset(
            {LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.METRIC_DASHBOARD, LayoutFamily.HERO}
        ),
        composition_bias=(
            CompositionBias.EVIDENCE_GRID,
            CompositionBias.CONCLUSION_BAR,
        ),
        copy_budget=CopyBudget(
            max_title_chars=32,
            max_message_chars=90,
            max_key_points=4,
            max_body_blocks=1,
        ),
        density=DensityLevel.COMPACT,
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        must_show=("photo_evidence_grid", "issue_labels", "problem_conclusion"),
        must_hide=("long_body_paragraphs", "decorative_icons"),
        title_patterns=(r"现状", r"现场", r"证据", r"evidence", r"踏勘"),
        body_patterns=(r"照片", r"编号", r"问题点", r"photo"),
        human_checklist=(
            "照片网格是否整齐可读",
            "结论条是否收束而非再堆字",
            "证据真实性是否被保护",
        ),
    ),
    ExpressionModeId.ANALYTICAL_DIAGRAM: ExpressionMode(
        id=ExpressionModeId.ANALYTICAL_DIAGRAM,
        display_name="Analytical Diagram",
        description="分析图主导，文字附属。",
        primary_family=LayoutFamily.ANALYTICAL_DIAGRAM,
        primary_variant="diagram_with_callouts",
        fallback_families=(LayoutFamily.DRAWING_FOCUS, LayoutFamily.HYBRID_CANVAS),
        forbidden_families=frozenset(
            {LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.METRIC_DASHBOARD}
        ),
        composition_bias=(CompositionBias.DIAGRAM_CENTER,),
        copy_budget=CopyBudget(
            max_title_chars=30,
            max_message_chars=70,
            max_key_points=3,
            max_body_blocks=1,
        ),
        density=DensityLevel.BALANCED,
        page_archetype=None,
        must_show=("analytical_diagram", "callouts", "one_line_reading"),
        must_hide=("photo_collage", "dense_bullet_wall"),
        title_patterns=(r"分析图", r"示意", r"流线分析", r"diagram", r"分析"),
        body_patterns=(r"关系", r"叠加", r"图层", r"callout"),
        human_checklist=(
            "图是否大于字",
            "标注是否服务读图",
            "是否像分析图而非装饰插画",
        ),
    ),
    ExpressionModeId.STRATEGY_CARDS: ExpressionMode(
        id=ExpressionModeId.STRATEGY_CARDS,
        display_name="Strategy Cards",
        description="3–4 策略卡，禁止堆字。",
        primary_family=LayoutFamily.STRATEGY_CARDS,
        primary_variant="strategy_concept",
        fallback_families=(LayoutFamily.HYBRID_CANVAS,),
        forbidden_families=frozenset(
            {LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.EVIDENCE_BOARD, LayoutFamily.HERO}
        ),
        composition_bias=(CompositionBias.STRATEGY_CARDS,),
        copy_budget=CopyBudget(
            max_title_chars=28,
            max_message_chars=64,
            max_key_points=4,
            max_body_blocks=0,
        ),
        density=DensityLevel.BALANCED,
        page_archetype=PageArchetype.DESIGN_STRATEGY,
        pair_role=PairRole.SOLUTION,
        must_show=("strategy_cards", "one_line_thesis"),
        must_hide=("long_body_paragraphs", "dense_bullet_wall"),
        title_patterns=(r"策略", r"原则", r"设计思路", r"strategy"),
        body_patterns=(r"策略一", r"策略二", r"卡片", r"principle"),
        human_checklist=(
            "卡片数量是否 3–4",
            "每卡是否一句可读",
            "是否回指问题而非空口号",
        ),
    ),
    ExpressionModeId.PROCESS_NARRATIVE: ExpressionMode(
        id=ExpressionModeId.PROCESS_NARRATIVE,
        display_name="Process Narrative",
        description="分期 / 流程横向叙事。",
        primary_family=LayoutFamily.PROCESS_NARRATIVE,
        primary_variant="steps_horizontal",
        fallback_families=(LayoutFamily.STRATEGY_CARDS,),
        forbidden_families=frozenset({LayoutFamily.HERO, LayoutFamily.EVIDENCE_BOARD}),
        composition_bias=(CompositionBias.TEXT_LEAD,),
        copy_budget=CopyBudget(
            max_title_chars=30,
            max_message_chars=80,
            max_key_points=5,
            max_body_blocks=1,
        ),
        density=DensityLevel.BALANCED,
        page_archetype=None,
        must_show=("process_steps", "phase_labels"),
        must_hide=("unordered_bullet_dump",),
        title_patterns=(r"分期", r"流程", r"实施", r"阶段", r"process", r"timeline"),
        body_patterns=(r"一期", r"二期", r"步骤", r"phase", r"step"),
        human_checklist=(
            "阶段是否横向可读",
            "时间/逻辑是否清晰",
            "是否避免竖排说明书感",
        ),
    ),
    ExpressionModeId.METRIC_DASHBOARD: ExpressionMode(
        id=ExpressionModeId.METRIC_DASHBOARD,
        display_name="Metric Dashboard",
        description="指标克制，服务决策页。",
        primary_family=LayoutFamily.METRIC_DASHBOARD,
        primary_variant="metric_cards",
        fallback_families=(LayoutFamily.STRATEGY_CARDS,),
        forbidden_families=frozenset({LayoutFamily.HERO, LayoutFamily.EVIDENCE_BOARD}),
        composition_bias=(CompositionBias.CONCLUSION_BAR,),
        copy_budget=CopyBudget(
            max_title_chars=28,
            max_message_chars=64,
            max_key_points=4,
            max_body_blocks=1,
        ),
        density=DensityLevel.COMPACT,
        page_archetype=None,
        must_show=("kpi_cards", "decision_takeaway"),
        must_hide=("chart_junk", "more_than_six_metrics"),
        title_patterns=(r"指标", r"数据", r"KPI", r"对标", r"metric"),
        body_patterns=(r"%", r"㎡", r"率", r"提升", r"对比"),
        human_checklist=(
            "指标是否 ≤4–6 且服务决策",
            "是否有一句决策结论",
            "是否避免仪表盘堆砌",
        ),
    ),
    ExpressionModeId.HYBRID_CLIMAX: ExpressionMode(
        id=ExpressionModeId.HYBRID_CLIMAX,
        display_name="Hybrid Climax",
        description="综合高潮页：严格容量预算，图文各司其职。",
        primary_family=LayoutFamily.HYBRID_CANVAS,
        primary_variant="freeform",
        fallback_families=(LayoutFamily.HERO, LayoutFamily.STRATEGY_CARDS),
        forbidden_families=frozenset({LayoutFamily.TEXTUAL_ARGUMENT}),
        composition_bias=(
            CompositionBias.PHOTO_LEFT,
            CompositionBias.CONCLUSION_BAR,
        ),
        copy_budget=CopyBudget(
            max_title_chars=28,
            max_message_chars=64,
            max_key_points=2,
            max_body_blocks=1,
        ),
        density=DensityLevel.SPACIOUS,
        page_archetype=None,
        must_show=("climax_visual", "single_thesis", "supporting_proof"),
        must_hide=("everything_on_one_page", "dense_caption_wall"),
        title_patterns=(r"高潮", r"效果", r"综合", r"愿景呈现", r"climax"),
        body_patterns=(r"因此", r"最终", r"呈现", r"综合表达"),
        human_checklist=(
            "是否形成全稿视觉高潮",
            "信息是否主动做减法",
            "是否像收束页而非杂烩页",
        ),
    ),
}


def list_expression_modes() -> tuple[ExpressionMode, ...]:
    return tuple(_MODES[item] for item in ExpressionModeId)


def get_expression_mode(mode_id: ExpressionModeId | str) -> ExpressionMode:
    key = resolve_expression_mode_id(mode_id)
    try:
        return _MODES[key]
    except KeyError as exc:
        raise KeyError(f"unknown expression mode: {mode_id}") from exc


def resolve_expression_mode_id(value: ExpressionModeId | str) -> ExpressionModeId:
    if isinstance(value, ExpressionModeId):
        return value
    cleaned = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    try:
        return ExpressionModeId(cleaned)
    except ValueError as exc:
        raise KeyError(f"unknown expression mode: {value}") from exc


def expression_mode_for_archetype(archetype: PageArchetype | None) -> ExpressionMode | None:
    """Best-effort map from PageArchetype to a primary expression mode."""
    if archetype is None or archetype == PageArchetype.GENERIC:
        return None
    mapping = {
        PageArchetype.NARRATIVE_OPENING: ExpressionModeId.HERO_OPENING,
        PageArchetype.SITE_CONTEXT_ANALYSIS: ExpressionModeId.DRAWING_STORY,
        PageArchetype.SITE_PROBLEM_DIAGNOSIS: ExpressionModeId.EVIDENCE_BOARD,
        PageArchetype.DESIGN_STRATEGY: ExpressionModeId.STRATEGY_CARDS,
        PageArchetype.BEFORE_AFTER_TRANSFORMATION: ExpressionModeId.BEFORE_AFTER,
    }
    mode_id = mapping.get(archetype)
    return _MODES[mode_id] if mode_id else None


def recognize_expression_mode(
    *,
    title: str = "",
    message: str = "",
    key_points: list[str] | None = None,
    page_archetype: PageArchetype | None = None,
) -> ExpressionMode | None:
    """Score title/body signals; fall back to archetype map."""
    blob_title = title or ""
    blob_body = " ".join([message or "", " ".join(key_points or [])])
    best: ExpressionMode | None = None
    best_score = 0.0

    for mode in list_expression_modes():
        score = 0.0
        for pattern in mode.title_patterns:
            if re.search(pattern, blob_title, re.I):
                score += 2.0
        for pattern in mode.body_patterns:
            if re.search(pattern, blob_body, re.I):
                score += 1.0
        if page_archetype and mode.page_archetype == page_archetype:
            score += 1.5
        if score > best_score:
            best_score = score
            best = mode

    if best is not None and best_score >= 2.0:
        return best

    mapped = expression_mode_for_archetype(page_archetype)
    return mapped
