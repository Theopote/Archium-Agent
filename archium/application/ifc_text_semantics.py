"""Lightweight IFC text semantics — counts entities without a full STEP graph."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_SCHEMA_RE = re.compile(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", re.IGNORECASE)
_ENTITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "space_count": re.compile(r"\bIFCSPACE\s*\(", re.IGNORECASE),
    "storey_count": re.compile(r"\bIFCBUILDINGSTOREY\s*\(", re.IGNORECASE),
    "building_count": re.compile(r"\bIFCBUILDING\s*\(", re.IGNORECASE),
    "wall_count": re.compile(r"\bIFCWALL(?:STANDARDCASE)?\s*\(", re.IGNORECASE),
    "door_count": re.compile(r"\bIFCDOOR\s*\(", re.IGNORECASE),
    "window_count": re.compile(r"\bIFCWINDOW\s*\(", re.IGNORECASE),
}

# Avoid loading huge binary-ish dumps into memory at once.
_DEFAULT_MAX_BYTES = 12_000_000


@dataclass(frozen=True)
class IfcTextSemantics:
    """Heuristic entity counts from IFC STEP text."""

    schema: str = ""
    space_count: int = 0
    storey_count: int = 0
    building_count: int = 0
    wall_count: int = 0
    door_count: int = 0
    window_count: int = 0
    bytes_scanned: int = 0
    truncated: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "space_count": self.space_count,
            "storey_count": self.storey_count,
            "building_count": self.building_count,
            "wall_count": self.wall_count,
            "door_count": self.door_count,
            "window_count": self.window_count,
            "bytes_scanned": self.bytes_scanned,
            "truncated": self.truncated,
            "parse_depth": "ifc_text_semantics",
        }

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        if self.schema:
            lines.append(f"IFC schema：{self.schema}")
        lines.append(
            f"空间/楼层/建筑：{self.space_count} / {self.storey_count} / {self.building_count}"
        )
        if self.wall_count or self.door_count or self.window_count:
            lines.append(
                f"墙/门/窗（实体计数）：{self.wall_count} / {self.door_count} / {self.window_count}"
            )
        lines.extend(self.notes)
        return lines


def extract_ifc_text_semantics(
    path: Path,
    *,
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> IfcTextSemantics:
    """Scan IFC STEP text for common entity tokens and FILE_SCHEMA."""
    path = path.expanduser()
    if not path.is_file():
        return IfcTextSemantics(notes=["文件不存在，无法扫描 IFC 文本"])

    size = path.stat().st_size
    truncated = size > max_bytes
    raw = path.read_bytes()[:max_bytes]
    text = raw.decode("utf-8", errors="ignore")
    if not text.strip():
        text = raw.decode("latin-1", errors="ignore")

    schema_match = _SCHEMA_RE.search(text)
    schema = schema_match.group(1).strip() if schema_match else ""

    counts = {key: len(pattern.findall(text)) for key, pattern in _ENTITY_PATTERNS.items()}
    notes = [
        "基于 STEP 文本实体计数（非几何/拓扑解析）",
    ]
    if truncated:
        notes.append(f"文件较大，仅扫描前 {max_bytes} bytes")
    if counts["space_count"] == 0 and counts["storey_count"] == 0:
        notes.append("未检出 IfcSpace / IfcBuildingStorey —— 可能是导出裁剪或非建筑模型")

    return IfcTextSemantics(
        schema=schema,
        space_count=counts["space_count"],
        storey_count=counts["storey_count"],
        building_count=counts["building_count"],
        wall_count=counts["wall_count"],
        door_count=counts["door_count"],
        window_count=counts["window_count"],
        bytes_scanned=len(raw),
        truncated=truncated,
        notes=notes,
    )
