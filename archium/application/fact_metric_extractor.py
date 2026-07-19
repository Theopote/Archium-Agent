"""Rule-based extraction of architectural metrics from document chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from archium.domain.document import DocumentChunk
from archium.domain.fact_ledger import STANDARD_FACT_KEY_MAP, STANDARD_FACT_KEYS

_RULE_CONFIDENCE = 0.92


@dataclass(frozen=True)
class ExtractedMetric:
    key: str
    label: str
    value: str
    unit: str | None
    category: str
    confidence: float
    chunk_id: UUID
    quote: str


@dataclass(frozen=True)
class _MetricPattern:
    key: str
    pattern: re.Pattern[str]
    unit_group: int | None = None


_METRIC_PATTERNS: tuple[_MetricPattern, ...] = (
    _MetricPattern("plot_ratio", re.compile(r"容积率[:：\s]*([0-9]+(?:\.[0-9]+)?)", re.I)),
    _MetricPattern(
        "plot_ratio",
        re.compile(r"\bFAR[:：\s]*([0-9]+(?:\.[0-9]+)?)", re.I),
    ),
    _MetricPattern(
        "height",
        re.compile(r"限高[:：\s]*([0-9]+(?:\.[0-9]+)?)\s*(米|m|M)?", re.I),
        unit_group=2,
    ),
    _MetricPattern(
        "height",
        re.compile(r"建筑高度[:：\s]*([0-9]+(?:\.[0-9]+)?)\s*(米|m|M)?", re.I),
        unit_group=2,
    ),
    _MetricPattern(
        "site_area",
        re.compile(
            r"用地面积(?:约)?[:：\s]*([0-9]+(?:\.[0-9]+)?)\s*(平方米|㎡|m2|m²|公顷|ha|亩)?",
            re.I,
        ),
        unit_group=2,
    ),
    _MetricPattern(
        "building_area",
        re.compile(
            r"建筑面积(?:约)?[:：\s]*([0-9]+(?:\.[0-9]+)?)\s*(平方米|㎡|m2|m²|公顷|ha|亩)?",
            re.I,
        ),
        unit_group=2,
    ),
    _MetricPattern(
        "building_density",
        re.compile(r"建筑密度[:：\s]*([0-9]+(?:\.[0-9]+)?)\s*(%|％)?", re.I),
        unit_group=2,
    ),
    _MetricPattern(
        "green_ratio",
        re.compile(r"绿地率[:：\s]*([0-9]+(?:\.[0-9]+)?)\s*(%|％)?", re.I),
        unit_group=2,
    ),
    _MetricPattern(
        "floors",
        re.compile(r"(?:地上)?层数[:：\s]*([0-9]+)\s*层?", re.I),
    ),
    _MetricPattern(
        "bed_count",
        re.compile(r"(?:规划)?床位(?:数)?[:：\s]*([0-9]+)\s*(张|个|床)?", re.I),
    ),
    _MetricPattern(
        "parking_count",
        re.compile(r"停车(?:位)?(?:数)?[:：\s]*([0-9]+)\s*(个|位)?", re.I),
    ),
)

_TABLE_LABEL_TO_KEY: dict[str, str] = {
    definition.label: definition.key for definition in STANDARD_FACT_KEYS
}
_TABLE_LABEL_TO_KEY.update(
    {
        "FAR": "plot_ratio",
        "容积率(FAR)": "plot_ratio",
        "用地": "site_area",
        "建筑面积(GFA)": "building_area",
        "绿地率/绿化率": "green_ratio",
        "绿化率": "green_ratio",
        "床位数": "bed_count",
        "停车位": "parking_count",
        "停车位数": "parking_count",
    }
)
_TABLE_VALUE_PATTERN = re.compile(
    r"^([0-9]+(?:\.[0-9]+)?)\s*(平方米|㎡|m2|m²|公顷|ha|亩|米|m|M|%|％|张|个|床|位|层)?$"
)


def extract_metrics_from_chunks(chunks: list[DocumentChunk]) -> list[ExtractedMetric]:
    """Scan chunk text for standard architectural metrics."""
    found: dict[str, ExtractedMetric] = {}
    for chunk in chunks:
        text = chunk.content.strip()
        if not text:
            continue
        for line in text.splitlines():
            table_metric = _extract_table_row_metric(line.strip(), chunk)
            if table_metric is not None:
                _store_metric(found, table_metric)
        for item in _METRIC_PATTERNS:
            match = item.pattern.search(text)
            if match is None:
                continue
            value = match.group(1).strip()
            if not value:
                continue
            unit = None
            if item.unit_group is not None and match.lastindex is not None:
                raw_unit = match.group(item.unit_group)
                unit = raw_unit.strip() if raw_unit else None
            definition = STANDARD_FACT_KEY_MAP.get(item.key)
            label = definition.label if definition else item.key
            category = definition.category if definition else "general"
            quote = _quote_window(text, match.start(), match.end())
            metric = ExtractedMetric(
                key=item.key,
                label=label,
                value=value,
                unit=_normalize_unit(unit),
                category=category,
                confidence=_RULE_CONFIDENCE,
                chunk_id=chunk.id,
                quote=quote,
            )
            _store_metric(found, metric)
    return list(found.values())


def _store_metric(found: dict[str, ExtractedMetric], metric: ExtractedMetric) -> None:
    existing = found.get(metric.key)
    if existing is None or metric.confidence >= existing.confidence:
        found[metric.key] = metric


def _extract_table_row_metric(line: str, chunk: DocumentChunk) -> ExtractedMetric | None:
    if "|" not in line and "\t" not in line:
        return None
    separator = "|" if "|" in line else "\t"
    parts = [part.strip() for part in line.split(separator) if part.strip()]
    if len(parts) < 2:
        return None
    label = parts[0]
    key = _TABLE_LABEL_TO_KEY.get(label)
    if key is None:
        for candidate, candidate_key in _TABLE_LABEL_TO_KEY.items():
            if candidate in label:
                key = candidate_key
                label = candidate
                break
    if key is None:
        return None
    value_text = parts[1]
    match = _TABLE_VALUE_PATTERN.match(value_text.replace(",", ""))
    if match is None:
        return None
    definition = STANDARD_FACT_KEY_MAP.get(key)
    return ExtractedMetric(
        key=key,
        label=definition.label if definition else label,
        value=match.group(1),
        unit=_normalize_unit(match.group(2)),
        category=definition.category if definition else "general",
        confidence=_RULE_CONFIDENCE,
        chunk_id=chunk.id,
        quote=line,
    )


def _quote_window(text: str, start: int, end: int, *, radius: int = 48) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].strip()


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    normalized = unit.strip()
    if not normalized:
        return None
    mapping = {
        "m": "米",
        "M": "米",
        "m2": "平方米",
        "m²": "平方米",
        "ha": "公顷",
        "%": "%",
        "％": "%",
    }
    return mapping.get(normalized, normalized)
