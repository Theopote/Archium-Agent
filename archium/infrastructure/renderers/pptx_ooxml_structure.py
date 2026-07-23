"""Validate native OOXML master / layout / slide relationship structure in a PPTX."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.pptx_structure import PptxStructureMode

_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

_REL_SLIDE_LAYOUT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
)
_REL_SLIDE_MASTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
)
_TARGET_MODE_EXTERNAL = "External"


class PptxOoxmlStructureReport(DomainModel):
    """Result of reading presentation.xml / slideMasters / slideLayouts / slide rels."""

    valid: bool
    structure_mode: PptxStructureMode
    master_parts: list[str] = Field(default_factory=list)
    layout_parts: list[str] = Field(default_factory=list)
    slide_parts: list[str] = Field(default_factory=list)
    slide_to_layout: dict[str, str] = Field(default_factory=dict)
    layout_to_master: dict[str, str] = Field(default_factory=dict)
    presentation_master_refs: list[str] = Field(default_factory=list)
    placeholder_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def inspect_pptx_ooxml_structure(pptx_path: Path | str) -> PptxOoxmlStructureReport:
    """Read OOXML package parts and relationship graph without PowerPoint."""
    path = Path(pptx_path)
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return PptxOoxmlStructureReport(
            valid=False,
            structure_mode=PptxStructureMode.FLAT,
            errors=[f"PPTX not found: {path}"],
        )

    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            master_parts = sorted(
                name
                for name in names
                if re.match(r"^ppt/slideMasters/slideMaster\d+\.xml$", name)
            )
            layout_parts = sorted(
                name
                for name in names
                if re.match(r"^ppt/slideLayouts/slideLayout\d+\.xml$", name)
            )
            slide_parts = sorted(
                name for name in names if re.match(r"^ppt/slides/slide\d+\.xml$", name)
            )

            if "ppt/presentation.xml" not in names:
                errors.append("missing ppt/presentation.xml")

            presentation_master_refs = _presentation_master_refs(archive, names, errors)
            slide_to_layout = _slide_to_layout_map(archive, slide_parts, names, errors)
            layout_to_master = _layout_to_master_map(archive, layout_parts, names, errors)
            placeholder_count = _count_placeholders(archive, layout_parts + master_parts)

            if not master_parts:
                errors.append("no ppt/slideMasters/slideMaster*.xml parts")
            if not layout_parts:
                errors.append("no ppt/slideLayouts/slideLayout*.xml parts")
            if slide_parts and not slide_to_layout:
                errors.append("slides/_rels does not reference any slideLayout")

            for slide_part, layout_target in slide_to_layout.items():
                layout_part = _resolve_zip_target(slide_part, layout_target)
                if layout_part not in names and layout_part not in layout_parts:
                    # PptxGen may use relative paths like ../slideLayouts/slideLayout1.xml
                    normalized = layout_part.lstrip("/")
                    if normalized not in names:
                        errors.append(
                            f"{slide_part} → layout target missing: {layout_target}"
                        )

            for layout_part, master_target in layout_to_master.items():
                master_part = _resolve_zip_target(layout_part, master_target)
                normalized = master_part.lstrip("/")
                if normalized not in names and master_part not in master_parts:
                    errors.append(
                        f"{layout_part} → master target missing: {master_target}"
                    )

            if len(master_parts) < 2:
                warnings.append(
                    f"only {len(master_parts)} slide master(s); structured catalogs "
                    "typically emit multiple masters"
                )
            if len(layout_parts) < 2:
                warnings.append(
                    f"only {len(layout_parts)} slide layout(s); structured catalogs "
                    "typically emit multiple layouts"
                )
            if placeholder_count == 0:
                warnings.append("no p:ph placeholders found on masters/layouts")

    except zipfile.BadZipFile as exc:
        return PptxOoxmlStructureReport(
            valid=False,
            structure_mode=PptxStructureMode.FLAT,
            errors=[f"invalid PPTX zip: {exc}"],
        )

    structured = (
        len(master_parts) >= 2
        and len(layout_parts) >= 2
        and bool(slide_to_layout)
        and bool(layout_to_master)
        and placeholder_count > 0
        and not errors
    )
    return PptxOoxmlStructureReport(
        valid=not errors,
        structure_mode=(
            PptxStructureMode.STRUCTURED if structured else PptxStructureMode.FLAT
        ),
        master_parts=master_parts,
        layout_parts=layout_parts,
        slide_parts=slide_parts,
        slide_to_layout=slide_to_layout,
        layout_to_master=layout_to_master,
        presentation_master_refs=presentation_master_refs,
        placeholder_count=placeholder_count,
        errors=errors,
        warnings=warnings,
    )


def require_structured_ooxml(pptx_path: Path | str) -> PptxOoxmlStructureReport:
    """Fail closed when STRUCTURED export did not produce a valid OOXML graph."""
    report = inspect_pptx_ooxml_structure(pptx_path)
    failures = list(report.errors)
    if report.structure_mode != PptxStructureMode.STRUCTURED:
        failures.append(
            "OOXML package is not STRUCTURED "
            f"(masters={len(report.master_parts)}, layouts={len(report.layout_parts)}, "
            f"placeholders={report.placeholder_count})"
        )
    if failures:
        raise ValueError("; ".join(failures))
    return report


def _presentation_master_refs(
    archive: zipfile.ZipFile,
    names: set[str],
    errors: list[str],
) -> list[str]:
    if "ppt/presentation.xml" not in names:
        return []
    root = ET.fromstring(archive.read("ppt/presentation.xml"))
    refs: list[str] = []
    for node in root.findall(".//p:sldMasterIdLst/p:sldMasterId", _NS):
        rid = node.attrib.get(f"{{{_NS['r']}}}id") or node.attrib.get("r:id")
        if rid:
            refs.append(rid)
    if not refs:
        errors.append("presentation.xml has empty p:sldMasterIdLst")
    return refs


def _slide_to_layout_map(
    archive: zipfile.ZipFile,
    slide_parts: list[str],
    names: set[str],
    errors: list[str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for slide_part in slide_parts:
        rels_part = _rels_path_for(slide_part)
        if rels_part not in names:
            errors.append(f"missing {rels_part}")
            continue
        target = _first_relationship_target(archive, rels_part, _REL_SLIDE_LAYOUT)
        if not target:
            errors.append(f"{rels_part} has no slideLayout relationship")
            continue
        mapping[slide_part] = target
    return mapping


def _layout_to_master_map(
    archive: zipfile.ZipFile,
    layout_parts: list[str],
    names: set[str],
    errors: list[str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for layout_part in layout_parts:
        rels_part = _rels_path_for(layout_part)
        if rels_part not in names:
            errors.append(f"missing {rels_part}")
            continue
        target = _first_relationship_target(archive, rels_part, _REL_SLIDE_MASTER)
        if not target:
            errors.append(f"{rels_part} has no slideMaster relationship")
            continue
        mapping[layout_part] = target
    return mapping


def _count_placeholders(archive: zipfile.ZipFile, parts: list[str]) -> int:
    count = 0
    for part in parts:
        try:
            root = ET.fromstring(archive.read(part))
        except ET.ParseError:
            continue
        count += len(root.findall(".//p:ph", _NS))
    return count


def _first_relationship_target(
    archive: zipfile.ZipFile,
    rels_part: str,
    relationship_type: str,
) -> str | None:
    root = ET.fromstring(archive.read(rels_part))
    for rel in root.findall("pr:Relationship", _NS):
        if rel.attrib.get("Type") != relationship_type:
            continue
        if rel.attrib.get("TargetMode") == _TARGET_MODE_EXTERNAL:
            continue
        target = rel.attrib.get("Target")
        if target:
            return target
    return None


def _rels_path_for(part: str) -> str:
    directory, _, filename = part.rpartition("/")
    return f"{directory}/_rels/{filename}.rels"


def _resolve_zip_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    source_dir = source_part.rsplit("/", 1)[0]
    parts = source_dir.split("/") + target.split("/")
    resolved: list[str] = []
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            if resolved:
                resolved.pop()
            continue
        resolved.append(part)
    return "/".join(resolved)
