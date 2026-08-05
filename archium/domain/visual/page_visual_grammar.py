"""Page-level visual grammar formulas — how a page *looks* as architectural speech.

Not LayoutFamily coordinates. A formula is a sentence of visual rhetoric:
semantic slots (Evidence + Conflict + Conclusion) → visual parts (photo + red accent).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class PageGrammarId(StrEnum):
    """Stable formula ids — grow carefully toward ~20 page languages."""

    PROBLEM_EVIDENCE_CONFLICT = "problem_evidence_conflict"
    STRATEGY_EXISTING_TRANSFORM = "strategy_existing_transform"
    PROCESS_SEQUENCE = "process_sequence"
    DRAWING_DOMINANT = "drawing_dominant"
    HERO_STATEMENT = "hero_statement"
    LAYER_ANALYSIS = "layer_analysis"
    PATH_EXPERIENCE = "path_experience"
    DECISION_METRIC = "decision_metric"
    MONUMENT_IMAGE = "monument_image"
    BEFORE_AFTER_CUT = "before_after_cut"
    CORE_EXPANSION = "core_expansion"
    QUIET_ARGUMENT = "quiet_argument"
    SECTION_OPENER = "section_opener"
    PHASING_TIMELINE = "phasing_timeline"
    THRESHOLD_SEQUENCE = "threshold_sequence"
    EVIDENCE_TRIPTYCH = "evidence_triptych"
    AXONOMETRIC_CALLOUT = "axonometric_callout"
    MASTERPLAN_FOCUS = "masterplan_focus"
    PROGRAM_STACK = "program_stack"
    QUOTE_CITATION = "quote_citation"


class PageVisualFormula(DomainModel):
    """One architectural presentation grammar sentence."""

    id: PageGrammarId
    display_name: str = Field(min_length=1, max_length=80)
    semantic_slots: list[str] = Field(default_factory=list, max_length=8)
    visual_parts: list[str] = Field(default_factory=list, max_length=10)
    accent_role: str = Field(default="conflict", max_length=32)
    preferred_emotions: list[str] = Field(default_factory=list, max_length=6)
    default_primitive_ids: list[str] = Field(default_factory=list, max_length=10)
    must_hide: list[str] = Field(default_factory=list, max_length=8)
    source: str = Field(default="page_grammar_v1", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id.value,
            "display_name": self.display_name,
            "semantic_slots": list(self.semantic_slots),
            "visual_parts": list(self.visual_parts),
            "accent_role": self.accent_role,
            "preferred_emotions": list(self.preferred_emotions),
            "default_primitive_ids": list(self.default_primitive_ids),
            "must_hide": list(self.must_hide),
            "source": self.source,
        }


FORMULA_PROBLEM = PageVisualFormula(
    id=PageGrammarId.PROBLEM_EVIDENCE_CONFLICT,
    display_name="问题页：证据 + 冲突 + 结论",
    semantic_slots=["Evidence", "Conflict", "Conclusion"],
    visual_parts=["photo", "diagram", "red_accent", "short_statement"],
    accent_role="conflict",
    preferred_emotions=["problem"],
    default_primitive_ids=["flow_line", "node", "axis_line", "thin_rule"],
    must_hide=["three_column_text", "metric_wall", "decorative_icons"],
)

FORMULA_STRATEGY = PageVisualFormula(
    id=PageGrammarId.STRATEGY_EXISTING_TRANSFORM,
    display_name="策略页：既有 + 转化 + 未来",
    semantic_slots=["Existing", "Transformation", "Future"],
    visual_parts=["before_image", "transition_arrow", "after_image"],
    accent_role="intervention",
    preferred_emotions=["strategy"],
    default_primitive_ids=[
        "transition_arrow",
        "thin_rule",
        "section_index",
        "overlay_map",
    ],
    must_hide=["emoji_icons", "long_body_paragraphs"],
)

FORMULA_PROCESS = PageVisualFormula(
    id=PageGrammarId.PROCESS_SEQUENCE,
    display_name="流程页：序列 + 演化 + 时间轴",
    semantic_slots=["Sequence", "Evolution", "Timeline"],
    visual_parts=["horizontal_axis", "nodes", "labels"],
    accent_role="accent",
    preferred_emotions=["strategy", "calm"],
    default_primitive_ids=["axis_line", "node", "section_index", "thin_rule"],
    must_hide=["photo_wall", "metric_wall"],
)

FORMULA_DRAWING = PageVisualFormula(
    id=PageGrammarId.DRAWING_DOMINANT,
    display_name="图纸页：主图 + 编号注解",
    semantic_slots=["PrimaryDrawing", "KeyedAnnotation", "NorthScale"],
    visual_parts=["drawing", "callouts", "thin_rule"],
    accent_role="neutral",
    preferred_emotions=["calm"],
    default_primitive_ids=["thin_rule", "axis_line", "section_index"],
    must_hide=["three_column_text", "strategy_card_wall"],
)

FORMULA_HERO = PageVisualFormula(
    id=PageGrammarId.HERO_STATEMENT,
    display_name="封面/高潮：一句主张 + 大图",
    semantic_slots=["Statement", "HeroImage"],
    visual_parts=["hero_statement", "full_bleed", "thin_rule"],
    accent_role="accent",
    preferred_emotions=["climax"],
    default_primitive_ids=["hero_statement", "thin_rule"],
    must_hide=["key_point_wall", "metric_wall"],
)

FORMULA_LAYER = PageVisualFormula(
    id=PageGrammarId.LAYER_ANALYSIS,
    display_name="分析页：底图 + 叠加层 + 结论",
    semantic_slots=["BaseMap", "Overlay", "Conclusion"],
    visual_parts=["overlay_map", "analysis_line", "short_statement"],
    accent_role="intervention",
    preferred_emotions=["calm", "problem"],
    default_primitive_ids=["overlay_map", "axis_line", "node", "thin_rule"],
    must_hide=["decorative_icons", "three_column_text"],
)

FORMULA_PATH = PageVisualFormula(
    id=PageGrammarId.PATH_EXPERIENCE,
    display_name="流线体验：路径 + 节点 + 空间序列",
    semantic_slots=["Path", "Node", "SpatialSequence"],
    visual_parts=["flow_line", "node", "sequence_labels"],
    accent_role="conflict",
    preferred_emotions=["problem", "strategy"],
    default_primitive_ids=[
        "flow_line",
        "node",
        "circulation",
        "entrance",
        "axis_line",
    ],
    must_hide=["emoji_icons", "metric_wall"],
)

FORMULA_DECISION = PageVisualFormula(
    id=PageGrammarId.DECISION_METRIC,
    display_name="决策页：克制指标 + 来源",
    semantic_slots=["Metric", "Comparison", "Source"],
    visual_parts=["metric_card", "thin_rule", "caption"],
    accent_role="accent",
    preferred_emotions=["decision"],
    default_primitive_ids=["thin_rule", "section_index"],
    must_hide=["photo_wall", "decorative_icons"],
)

FORMULA_MONUMENT = PageVisualFormula(
    id=PageGrammarId.MONUMENT_IMAGE,
    display_name="纪念碑图：一张大图 + 一句",
    semantic_slots=["MonumentImage", "OneLineClaim"],
    visual_parts=["hero_full", "short_statement", "silhouette"],
    accent_role="accent",
    preferred_emotions=["climax"],
    default_primitive_ids=["hero_statement", "thin_rule"],
    must_hide=["key_point_wall", "metric_wall", "strategy_card_wall"],
)

FORMULA_BEFORE_AFTER = PageVisualFormula(
    id=PageGrammarId.BEFORE_AFTER_CUT,
    display_name="前后对比：既有 / 切割 / 更新",
    semantic_slots=["Before", "Cut", "After"],
    visual_parts=["before_image", "transition_arrow", "after_image", "gradient_fade"],
    accent_role="intervention",
    preferred_emotions=["strategy", "climax"],
    default_primitive_ids=["transition_arrow", "thin_rule", "overlay_map"],
    must_hide=["emoji_icons", "three_column_text"],
)

FORMULA_CORE = PageVisualFormula(
    id=PageGrammarId.CORE_EXPANSION,
    display_name="核心生长：核体 + 扩展",
    semantic_slots=["Core", "Growth", "Expansion"],
    visual_parts=["circle_mask", "radial_nodes", "transition_arrow"],
    accent_role="intervention",
    preferred_emotions=["strategy", "climax"],
    default_primitive_ids=["node", "transition_arrow", "overlay_map", "thin_rule"],
    must_hide=["metric_wall", "emoji_icons"],
)

FORMULA_QUIET = PageVisualFormula(
    id=PageGrammarId.QUIET_ARGUMENT,
    display_name="克制主张：一句 + 留白",
    semantic_slots=["Claim", "Whitespace", "Source"],
    visual_parts=["short_statement", "thin_rule"],
    accent_role="neutral",
    preferred_emotions=["calm"],
    default_primitive_ids=["thin_rule", "section_index"],
    must_hide=["decorative_icons", "photo_wall", "strategy_card_wall"],
)

FORMULA_SECTION = PageVisualFormula(
    id=PageGrammarId.SECTION_OPENER,
    display_name="章节扉页：编号 + 短题",
    semantic_slots=["SectionIndex", "ShortTitle", "Whitespace"],
    visual_parts=["section_index", "thin_rule", "short_statement"],
    accent_role="neutral",
    preferred_emotions=["calm", "climax"],
    default_primitive_ids=["section_index", "thin_rule", "hero_statement"],
    must_hide=["key_point_wall", "metric_wall", "photo_wall"],
)

FORMULA_PHASING = PageVisualFormula(
    id=PageGrammarId.PHASING_TIMELINE,
    display_name="分期实施：阶段轴 + 节点",
    semantic_slots=["Phase", "Sequence", "Milestone"],
    visual_parts=["horizontal_axis", "nodes", "phase_labels"],
    accent_role="intervention",
    preferred_emotions=["strategy", "decision"],
    default_primitive_ids=["axis_line", "node", "section_index", "thin_rule"],
    must_hide=["emoji_icons", "photo_wall"],
)

FORMULA_THRESHOLD = PageVisualFormula(
    id=PageGrammarId.THRESHOLD_SEQUENCE,
    display_name="入口序列：门槛 + 路径 + 到达",
    semantic_slots=["Threshold", "Approach", "Arrival"],
    visual_parts=["entrance", "flow_line", "node"],
    accent_role="accent",
    preferred_emotions=["strategy", "calm"],
    default_primitive_ids=["entrance", "flow_line", "circulation", "node"],
    must_hide=["metric_wall", "three_column_text"],
)

FORMULA_EVIDENCE_TRIPTYCH = PageVisualFormula(
    id=PageGrammarId.EVIDENCE_TRIPTYCH,
    display_name="证据三联：三帧图像证据（非三栏字墙）",
    semantic_slots=["EvidenceA", "EvidenceB", "EvidenceC", "Claim"],
    visual_parts=["photo_triptych", "thin_rule", "short_statement"],
    accent_role="conflict",
    preferred_emotions=["problem"],
    default_primitive_ids=["thin_rule", "node", "axis_line"],
    must_hide=["three_column_text", "emoji_icons", "strategy_card_wall"],
)

FORMULA_AXON = PageVisualFormula(
    id=PageGrammarId.AXONOMETRIC_CALLOUT,
    display_name="轴测注解：体量 + 编号引出",
    semantic_slots=["Axonometric", "KeyedCallout", "Claim"],
    visual_parts=["drawing", "callouts", "thin_rule", "section_index"],
    accent_role="intervention",
    preferred_emotions=["strategy", "calm"],
    default_primitive_ids=["thin_rule", "node", "section_index", "overlay_map"],
    must_hide=["emoji_icons", "metric_wall", "three_column_text"],
)

FORMULA_MASTERPLAN = PageVisualFormula(
    id=PageGrammarId.MASTERPLAN_FOCUS,
    display_name="总图主导：场地平面 + 北向比例",
    semantic_slots=["Masterplan", "NorthScale", "Highlight"],
    visual_parts=["drawing", "axis_line", "overlay_map"],
    accent_role="intervention",
    preferred_emotions=["calm", "problem"],
    default_primitive_ids=["axis_line", "overlay_map", "node", "thin_rule"],
    must_hide=["strategy_card_wall", "emoji_icons"],
)

FORMULA_PROGRAM = PageVisualFormula(
    id=PageGrammarId.PROGRAM_STACK,
    display_name="功能叠合：竖向程序 + 分区色",
    semantic_slots=["Program", "Stack", "Zone"],
    visual_parts=["stack_diagram", "color_blocks", "thin_rule"],
    accent_role="accent",
    preferred_emotions=["strategy", "decision"],
    default_primitive_ids=["thin_rule", "section_index", "node", "overlay_map"],
    must_hide=["photo_wall", "emoji_icons"],
)

FORMULA_QUOTE = PageVisualFormula(
    id=PageGrammarId.QUOTE_CITATION,
    display_name="引语页：一句引用 + 来源",
    semantic_slots=["Quote", "Attribution", "Whitespace"],
    visual_parts=["short_statement", "thin_rule", "caption"],
    accent_role="neutral",
    preferred_emotions=["calm"],
    default_primitive_ids=["thin_rule", "hero_statement"],
    must_hide=["metric_wall", "photo_wall", "strategy_card_wall"],
)

_FORMULAS: dict[PageGrammarId, PageVisualFormula] = {
    f.id: f
    for f in (
        FORMULA_PROBLEM,
        FORMULA_STRATEGY,
        FORMULA_PROCESS,
        FORMULA_DRAWING,
        FORMULA_HERO,
        FORMULA_LAYER,
        FORMULA_PATH,
        FORMULA_DECISION,
        FORMULA_MONUMENT,
        FORMULA_BEFORE_AFTER,
        FORMULA_CORE,
        FORMULA_QUIET,
        FORMULA_SECTION,
        FORMULA_PHASING,
        FORMULA_THRESHOLD,
        FORMULA_EVIDENCE_TRIPTYCH,
        FORMULA_AXON,
        FORMULA_MASTERPLAN,
        FORMULA_PROGRAM,
        FORMULA_QUOTE,
    )
}


def get_page_formula(formula_id: PageGrammarId | str) -> PageVisualFormula:
    key = (
        formula_id
        if isinstance(formula_id, PageGrammarId)
        else PageGrammarId(str(formula_id))
    )
    return _FORMULAS[key]


def list_page_formulas() -> list[PageVisualFormula]:
    return list(_FORMULAS.values())


def select_page_formula(
    *,
    emotion: str,
    situation_rule_id: str | None = None,
    expression_mode_id: str | None = None,
    metaphor: str | None = None,
    title: str | None = None,
    continuity_role: str | None = None,
) -> PageVisualFormula:
    """Deterministic formula pick — concept/metaphor wins, then situation, then emotion."""
    title = (title or "").strip()
    metaphor = (metaphor or "").strip()
    rule = situation_rule_id or ""
    mode = expression_mode_id or ""
    emotion_key = (emotion or "calm").strip().lower()
    continuity = (continuity_role or "").strip().lower()

    if continuity in {"section_opening", "transition"} or title in {
        "章节",
        "第一章",
        "第二节",
        "篇章扉页",
        "问题篇",
        "策略篇",
    }:
        return FORMULA_SECTION
    if metaphor == "fragment_to_network" or title in {"流线冲突", "交通冲突", "人车混行"}:
        return FORMULA_PATH
    if metaphor == "core_to_expansion" or title in {"概念生成", "空间生长", "核心拓展"}:
        return FORMULA_CORE
    if metaphor == "existing_to_transformation" or title in {
        "效果表达",
        "更新前后",
        "改造对比",
    }:
        return FORMULA_BEFORE_AFTER if title in {"更新前后", "改造对比"} else FORMULA_STRATEGY
    if metaphor == "quiet_argument" or title in {"结论建议", "下一步", "总结"}:
        return FORMULA_QUIET
    if metaphor == "layered_site" or title in {"区位与交通", "城市分析", "分层分析"}:
        return FORMULA_LAYER
    if metaphor == "path_to_experience" or title in {"流线优化", "空间序列", "参观流线"}:
        return FORMULA_PATH
    if metaphor == "monument_single" or title in {"总体愿景"}:
        return FORMULA_MONUMENT
    if title in {"实施分期", "分期建设", "施工阶段", "实施计划"}:
        return FORMULA_PHASING
    if title in {"入口序列", "入院体验", "门槛空间", "到达体验"}:
        return FORMULA_THRESHOLD
    if title in {"证据三联", "现场三联", "问题三联"}:
        return FORMULA_EVIDENCE_TRIPTYCH
    if title in {"轴测分析", "体量轴测", "空间轴测"}:
        return FORMULA_AXON
    if title in {"总平面", "总图", "场地总图", "总体规划"}:
        return FORMULA_MASTERPLAN
    if title in {"功能构成", "功能叠合", "程序分区", "竖向功能"}:
        return FORMULA_PROGRAM
    if title in {"设计语录", "引用", "理念引语"}:
        return FORMULA_QUOTE
    if rule == "hero_opening" or title == "封面" or mode == "hero_opening":
        return FORMULA_HERO
    if rule == "drawing_story" or mode == "drawing_story":
        return FORMULA_DRAWING
    if rule == "site_problem_evidence" or mode == "evidence_board":
        return FORMULA_PROBLEM
    if rule == "site_traffic_conflict":
        return FORMULA_PATH
    if mode == "process_narrative":
        return FORMULA_PROCESS
    if mode == "before_after":
        return FORMULA_BEFORE_AFTER
    if mode == "metric_dashboard" or emotion_key == "decision":
        return FORMULA_DECISION
    if emotion_key == "strategy" or mode == "strategy_cards":
        return FORMULA_STRATEGY
    if emotion_key == "problem":
        return FORMULA_PROBLEM
    if emotion_key == "climax":
        return FORMULA_MONUMENT if title else FORMULA_HERO
    if emotion_key == "calm":
        return FORMULA_DRAWING
    return FORMULA_PROBLEM
