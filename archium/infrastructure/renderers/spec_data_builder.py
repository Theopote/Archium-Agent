"""Build chart and table payloads for PresentationSpec export."""

from __future__ import annotations

import re

from archium.domain.enums import SlideType, VerificationStatus, VisualType
from archium.domain.fact import ProjectFact
from archium.domain.presentation_spec import SpecChart, SpecChartSeries, SpecTable
from archium.domain.slide import SlideSpec

_LABEL_SPLIT_PATTERN = re.compile(r"^([^：:|]+)[：:|]\s*(.+)$")
_NUMERIC_PATTERN = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_TABLE_ROW_SPLIT_PATTERN = re.compile(r"[|｜]")


def parse_labeled_point(text: str) -> tuple[str, str] | None:
    match = _LABEL_SPLIT_PATTERN.match(text.strip())
    if match is None:
        return None
    return match.group(1).strip(), match.group(2).strip()


def parse_numeric_value(text: str) -> float | None:
    """Extract the first numeric literal from a value string."""
    normalized = text.replace(",", "").replace("，", "")
    match = _NUMERIC_PATTERN.search(normalized)
    if match is None:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def usable_facts(facts: list[ProjectFact]) -> list[ProjectFact]:
    excluded = {VerificationStatus.REJECTED, VerificationStatus.CONFLICTED}
    return [fact for fact in facts if fact.verification_status not in excluded]


def facts_matching_slide(slide: SlideSpec, facts: list[ProjectFact]) -> list[ProjectFact]:
    """Return facts whose labels appear in the slide title, message, or key points."""
    searchable = " ".join([slide.title, slide.message, *slide.key_points]).lower()
    matched: list[ProjectFact] = []
    seen: set[str] = set()

    for fact in facts:
        if fact.key in seen:
            continue
        label_hit = fact.label.lower() in searchable
        key_hit = fact.key.replace("_", " ") in searchable
        if label_hit or key_hit:
            matched.append(fact)
            seen.add(fact.key)

    if matched:
        return matched

    for point in slide.key_points:
        parsed = parse_labeled_point(point)
        if parsed is None:
            continue
        label = parsed[0]
        for fact in facts:
            if fact.key in seen:
                continue
            if label == fact.label or label in fact.label or fact.label in label:
                matched.append(fact)
                seen.add(fact.key)
    return matched


def _format_fact_value(fact: ProjectFact) -> str:
    if isinstance(fact.value, bool):
        return "是" if fact.value else "否"
    if isinstance(fact.value, (int, float)):
        text = str(fact.value)
        return f"{text}{fact.unit}" if fact.unit else text
    if isinstance(fact.value, str):
        return f"{fact.value}{fact.unit or ''}"
    return str(fact.value)


def _numeric_fact_value(fact: ProjectFact) -> float | None:
    if isinstance(fact.value, bool):
        return None
    if isinstance(fact.value, (int, float)):
        return float(fact.value)
    if isinstance(fact.value, str):
        return parse_numeric_value(fact.value)
    return None


def _infer_chart_type(slide: SlideSpec, labels: list[str]) -> str:
    haystack = f"{slide.title} {slide.message} {' '.join(labels)}"
    if any(token in haystack for token in ("占比", "比例", "构成", "分布", "%")):
        return "pie"
    if any(token in haystack for token in ("趋势", "变化", "增长", "走势")):
        return "line"
    return "bar"


def build_chart(slide: SlideSpec, facts: list[ProjectFact] | None = None) -> SpecChart | None:
    """Build a native chart from confirmed facts first, then labeled key points."""
    active_facts = usable_facts(facts or [])
    matched_facts = facts_matching_slide(slide, active_facts)

    labels: list[str] = []
    values: list[float] = []
    for fact in matched_facts:
        numeric = _numeric_fact_value(fact)
        if numeric is None:
            continue
        labels.append(fact.label)
        values.append(numeric)

    if len(labels) < 2:
        labels = []
        values = []
        for point in slide.key_points:
            parsed = parse_labeled_point(point)
            if parsed is None:
                continue
            numeric = parse_numeric_value(parsed[1])
            if numeric is None:
                continue
            labels.append(parsed[0])
            values.append(numeric)

    if len(labels) < 2:
        return None

    chart_type = _infer_chart_type(slide, labels)
    return SpecChart(
        chart_type=chart_type,
        title=slide.title,
        series=[SpecChartSeries(name="核心指标", labels=labels, values=values)],
        show_legend=chart_type != "bar",
        show_value=True,
    )


def build_table(slide: SlideSpec, facts: list[ProjectFact] | None = None) -> SpecTable | None:
    """Build a native table from facts or structured key points."""
    active_facts = usable_facts(facts or [])
    matched_facts = facts_matching_slide(slide, active_facts)

    if matched_facts:
        rows = [[fact.label, _format_fact_value(fact), fact.unit or ""] for fact in matched_facts]
        return SpecTable(headers=["指标", "数值", "单位"], rows=rows)

    if _primary_visual_type(slide) == VisualType.TABLE and active_facts:
        rows = [[fact.label, _format_fact_value(fact), fact.unit or ""] for fact in active_facts[:8]]
        return SpecTable(headers=["指标", "数值", "单位"], rows=rows)

    pipe_rows: list[list[str]] = []
    labeled_rows: list[list[str]] = []
    for point in slide.key_points:
        if _TABLE_ROW_SPLIT_PATTERN.search(point):
            cells = [cell.strip() for cell in _TABLE_ROW_SPLIT_PATTERN.split(point) if cell.strip()]
            if len(cells) >= 2:
                pipe_rows.append(cells)
            continue
        parsed = parse_labeled_point(point)
        if parsed is not None:
            labeled_rows.append([parsed[0], parsed[1]])
        else:
            labeled_rows.append([point, "—"])

    if pipe_rows:
        if len(pipe_rows) >= 2 and all(len(row) == len(pipe_rows[0]) for row in pipe_rows):
            return SpecTable(headers=pipe_rows[0], rows=pipe_rows[1:])
        return SpecTable(headers=["列 1", "列 2", "列 3"][: len(pipe_rows[0])], rows=pipe_rows)

    if labeled_rows:
        return SpecTable(headers=["指标", "数值"], rows=labeled_rows)

    return None


def resolve_numeric_layout(slide: SlideSpec, facts: list[ProjectFact] | None = None) -> str | None:
    """Return chart/table/data layout when the slide carries numeric intent."""
    primary_visual = _primary_visual_type(slide)
    if primary_visual == VisualType.CHART:
        return _LAYOUT_CHART if build_chart(slide, facts) is not None else None
    if primary_visual == VisualType.TABLE:
        return _LAYOUT_TABLE if build_table(slide, facts) is not None else None
    if slide.slide_type == SlideType.DATA:
        if build_chart(slide, facts) is not None:
            return _LAYOUT_CHART
        return _LAYOUT_DATA
    return None


_LAYOUT_CHART = "chart"
_LAYOUT_TABLE = "table"
_LAYOUT_DATA = "data"


def preferred_data_layout(slide: SlideSpec, facts: list[ProjectFact] | None = None) -> str:
    """Backward-compatible alias for numeric layout resolution."""
    resolved = resolve_numeric_layout(slide, facts)
    return resolved or _LAYOUT_DATA


def _primary_visual_type(slide: SlideSpec) -> VisualType | None:
    for requirement in slide.visual_requirements:
        if requirement.type != VisualType.TEXT_ONLY:
            return requirement.type
    return None
