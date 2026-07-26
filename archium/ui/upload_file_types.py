"""Shared Streamlit file_uploader type lists for project materials."""

from __future__ import annotations

# Office + images (M1) + CAD/BIM suffixes (Topic 05 Phase M2 / APP-020).
# Backend CadBimParser already accepts these; UI must list them for Streamlit.
PROJECT_MATERIAL_UPLOAD_TYPES: list[str] = [
    "pdf",
    "docx",
    "pptx",
    "xlsx",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "dwg",
    "dxf",
    "ifc",
    "rvt",
    "rfa",
]

PROJECT_MATERIAL_UPLOAD_CAPTION = (
    "支持 PDF/Office/图片，以及 DWG/DXF/IFC/RVT（CAD/BIM 以元数据与 IFC 文本入库，"
    "完整几何解析后续迭代）。现场图/图纸可记为探索弱种子，不会自动选定方向。"
)
