"""CAD / BIM metadata extraction — knowledge registration without full geometry parse."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from archium.domain.enums import DocumentType


@dataclass(frozen=True)
class CadAssetAnalysis:
    """Structured stub analysis for CAD/BIM files (not a full model parser)."""

    format: str
    document_type: DocumentType
    file_name: str
    size_bytes: int
    notes: list[str] = field(default_factory=list)
    analysis: dict[str, object] = field(default_factory=dict)

    def as_metadata(self) -> dict[str, object]:
        depth = str(self.analysis.get("parse_depth") or "metadata_only")
        return {
            "cad_bim": True,
            "format": self.format,
            "document_type": self.document_type.value,
            "size_bytes": self.size_bytes,
            "notes": list(self.notes),
            "analysis": dict(self.analysis),
            "parse_depth": depth,
        }

    def summary_text(self) -> str:
        bits = [
            f"CAD/BIM 资产：{self.file_name}",
            f"格式：{self.format}",
            f"大小：{self.size_bytes} bytes",
        ]
        bits.extend(self.notes)
        for key, value in list(self.analysis.items())[:8]:
            bits.append(f"{key}：{value}")
        bits.append("完整几何解析尚未启用；当前作为知识来源登记。")
        return "\n".join(bits)


_CAD_SUFFIX_MAP: dict[str, tuple[DocumentType, str]] = {
    ".dwg": (DocumentType.DWG, "AutoCAD DWG"),
    ".dxf": (DocumentType.DXF, "AutoCAD DXF"),
    ".ifc": (DocumentType.IFC, "Industry Foundation Classes"),
    ".rvt": (DocumentType.RVT, "Revit project"),
    ".rfa": (DocumentType.RVT, "Revit family"),
}


def is_cad_bim_path(path: Path) -> bool:
    return path.suffix.lower() in _CAD_SUFFIX_MAP


def analyze_cad_bim_file(path: Path) -> CadAssetAnalysis:
    """Extract registration metadata for CAD/BIM uploads.

    IFC files get lightweight STEP text entity counts; full geometry stays deferred.
    """
    path = path.expanduser()
    suffix = path.suffix.lower()
    doc_type, format_label = _CAD_SUFFIX_MAP.get(
        suffix, (DocumentType.OTHER, suffix.lstrip(".") or "unknown")
    )
    size = path.stat().st_size if path.is_file() else 0
    notes = [
        "已识别为建筑设计文件资产",
        "可绑定到项目知识与页证据，后续可接几何/空间解析器",
    ]
    analysis: dict[str, object] = {
        "suffix": suffix,
        "likely_domain": "architecture",
    }
    if doc_type == DocumentType.IFC:
        analysis["schema_family"] = "IFC"
        from archium.application.ifc_text_semantics import extract_ifc_text_semantics

        semantics = extract_ifc_text_semantics(path)
        analysis["ifc_semantics"] = semantics.as_dict()
        analysis["schema"] = semantics.schema
        analysis["space_count"] = semantics.space_count
        analysis["storey_count"] = semantics.storey_count
        analysis["parse_depth"] = "ifc_text_semantics"
        notes.extend(semantics.summary_lines())
    elif doc_type == DocumentType.RVT:
        analysis["authoring_tool"] = "Revit"
        notes.append("RVT：专有格式，建议导出 IFC/PDF 后再做深度知识抽取")
    elif doc_type in {DocumentType.DWG, DocumentType.DXF}:
        analysis["authoring_tool"] = "CAD"
        notes.append("DWG/DXF：建议配合图纸用途标注（平面/剖面/详图）")

    return CadAssetAnalysis(
        format=format_label,
        document_type=doc_type,
        file_name=path.name,
        size_bytes=size,
        notes=notes,
        analysis=analysis,
    )
