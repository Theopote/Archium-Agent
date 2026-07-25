"""Architectural chunk typing — retrieve design knowledge, not bare text."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class ArchitecturalChunkType(StrEnum):
    """Semantic role of a document chunk for architectural retrieval."""

    CASE_BACKGROUND = "case_background"
    DESIGN_CONCEPT = "design_concept"
    SPATIAL_STRATEGY = "spatial_strategy"
    MATERIAL_STRATEGY = "material_strategy"
    CONSTRUCTION_LOGIC = "construction_logic"
    USER_EXPERIENCE = "user_experience"
    METRICS = "metrics"
    REGULATION = "regulation"
    DRAWING_NOTE = "drawing_note"
    GENERAL = "general"


# (type, weight hints) — first match with highest score wins
_TYPE_HINTS: dict[ArchitecturalChunkType, tuple[str, ...]] = {
    ArchitecturalChunkType.DRAWING_NOTE: (
        "图纸",
        "平面图",
        "总平面",
        "剖面",
        "立面",
        "site plan",
        "drawing",
        "图示",
    ),
    ArchitecturalChunkType.METRICS: (
        "容积率",
        "建筑密度",
        "用地面积",
        "建筑面积",
        "绿地率",
        "限高",
        "指标",
        "gfa",
        "plot ratio",
        "㎡",
        "m²",
    ),
    ArchitecturalChunkType.REGULATION: (
        "规范",
        "条例",
        "规划条件",
        "控规",
        "退线",
        "红线",
        "防火",
        "强制",
        "regulation",
        "code",
    ),
    ArchitecturalChunkType.SPATIAL_STRATEGY: (
        "空间",
        "院落",
        "流线",
        "轴线",
        "围合",
        "庭院",
        "路径",
        "层级",
        "spatial",
        "courtyard",
        "circulation",
        "axis",
    ),
    ArchitecturalChunkType.MATERIAL_STRATEGY: (
        "材料",
        "构造",
        "砖",
        "木构",
        "混凝土",
        "瓦",
        "表皮",
        "tectonic",
        "material",
        "cladding",
    ),
    ArchitecturalChunkType.CONSTRUCTION_LOGIC: (
        "结构",
        "施工",
        "建造",
        "抗震",
        "基础",
        "框架",
        "structure",
        "construction",
        "seismic",
    ),
    ArchitecturalChunkType.USER_EXPERIENCE: (
        "体验",
        "氛围",
        "行为",
        "使用",
        "访客",
        "停留",
        "atmosphere",
        "experience",
        "occupancy",
    ),
    ArchitecturalChunkType.DESIGN_CONCEPT: (
        "理念",
        "概念",
        "策略",
        "设计意图",
        "concept",
        "design intent",
        "idea",
        "rationale",
    ),
    ArchitecturalChunkType.CASE_BACKGROUND: (
        "背景",
        "概况",
        "区位",
        "历史",
        "业主",
        "background",
        "context",
        "site history",
    ),
}

_QUERY_TYPE_HINTS: dict[ArchitecturalChunkType, tuple[str, ...]] = {
    ArchitecturalChunkType.SPATIAL_STRATEGY: (
        "空间",
        "院落",
        "流线",
        "布局",
        "spatial",
        "courtyard",
    ),
    ArchitecturalChunkType.MATERIAL_STRATEGY: ("材料", "构造", "material", "tectonic"),
    ArchitecturalChunkType.METRICS: ("指标", "面积", "容积率", "限高", "metrics"),
    ArchitecturalChunkType.REGULATION: ("规范", "规划条件", "退线", "控规"),
    ArchitecturalChunkType.DRAWING_NOTE: ("图纸", "平面", "剖面", "drawing", "plan"),
    ArchitecturalChunkType.DESIGN_CONCEPT: ("概念", "理念", "策略", "concept"),
    ArchitecturalChunkType.USER_EXPERIENCE: ("体验", "氛围", "行为"),
    ArchitecturalChunkType.CONSTRUCTION_LOGIC: ("结构", "建造", "施工"),
    ArchitecturalChunkType.CASE_BACKGROUND: ("背景", "案例", "概况"),
}


class ArchitecturalChunkAnnotation(DomainModel):
    """Typed annotation attached to a DocumentChunk (via metadata)."""

    chunk_type: ArchitecturalChunkType = ArchitecturalChunkType.GENERAL
    design_topics: list[str] = Field(default_factory=list)
    related_objects: list[str] = Field(default_factory=list)

    def to_metadata(self) -> dict[str, object]:
        return {
            "architectural_type": self.chunk_type.value,
            "design_topics": list(self.design_topics)[:8],
            "related_objects": list(self.related_objects)[:8],
        }


def classify_architectural_chunk(
    content: str,
    *,
    section_title: str | None = None,
    content_type: str = "text",
) -> ArchitecturalChunkAnnotation:
    """Rule-based classifier — prefer section cues, then body keywords."""
    if (content_type or "").strip().lower() in {"asset_caption", "image", "drawing"}:
        return ArchitecturalChunkAnnotation(
            chunk_type=ArchitecturalChunkType.DRAWING_NOTE,
            design_topics=_extract_topics(content, section_title),
        )

    haystack = f"{section_title or ''}\n{content or ''}".lower()
    best_type = ArchitecturalChunkType.GENERAL
    best_score = 0
    for chunk_type, hints in _TYPE_HINTS.items():
        score = sum(1 for hint in hints if hint.lower() in haystack)
        if score > best_score:
            best_score = score
            best_type = chunk_type

    if best_score <= 0:
        best_type = ArchitecturalChunkType.GENERAL

    return ArchitecturalChunkAnnotation(
        chunk_type=best_type,
        design_topics=_extract_topics(content, section_title),
    )


def infer_types_from_query(query: str) -> list[ArchitecturalChunkType]:
    """Soft preferences for hybrid retrieval (not a hard filter)."""
    text = (query or "").strip().lower()
    if not text:
        return []
    matched: list[ArchitecturalChunkType] = []
    for chunk_type, hints in _QUERY_TYPE_HINTS.items():
        if any(hint.lower() in text for hint in hints):
            matched.append(chunk_type)
    return matched


def architectural_type_from_metadata(metadata: dict[str, object] | None) -> ArchitecturalChunkType:
    raw = (metadata or {}).get("architectural_type") or (metadata or {}).get("chunk_type")
    if raw is None:
        return ArchitecturalChunkType.GENERAL
    try:
        return ArchitecturalChunkType(str(raw).strip())
    except ValueError:
        return ArchitecturalChunkType.GENERAL


def _extract_topics(content: str, section_title: str | None) -> list[str]:
    topics: list[str] = []
    if section_title and section_title.strip():
        topics.append(section_title.strip()[:40])
    blob = f"{section_title or ''} {content or ''}"
    for token in (
        "院落",
        "流线",
        "材料",
        "轴线",
        "庭院",
        "台地",
        "退台",
        "围合",
        "courtyard",
        "circulation",
    ):
        if token.lower() in blob.lower() and token not in topics:
            topics.append(token)
    return topics[:8]
