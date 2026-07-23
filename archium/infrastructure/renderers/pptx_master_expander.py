"""Expand a PptxGenJS PPTX so each declared SlideMasterSpec becomes a real master part.

PptxGenJS emits multiple named slide layouts with placeholders, but collapses them
under a single ``slideMaster1.xml``. This post-processor clones masters, rewires
Layout → Master relationships from ``PresentationStructureSpec``, and updates
``presentation.xml`` / Content_Types so OOXML reflects Slide → Layout → Master.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from archium.domain.visual.pptx_structure import PresentationStructureSpec, PptxStructureMode

_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

_REL_SLIDE_MASTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
)
_REL_SLIDE_LAYOUT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
)
_REL_THEME = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
_CT_SLIDE_MASTER = (
    "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"
)

for _prefix, _uri in _NS.items():
    ET.register_namespace(_prefix if _prefix != "pr" else "", _uri)
ET.register_namespace("", _NS["pr"])
ET.register_namespace("p", _NS["p"])
ET.register_namespace("r", _NS["r"])
ET.register_namespace("a", _NS["a"])


def expand_masters_from_structure(
    pptx_path: Path | str,
    structure: PresentationStructureSpec,
    *,
    output_path: Path | str | None = None,
) -> Path:
    """Clone slide masters so each structure master_id has a real OOXML part."""
    source = Path(pptx_path)
    target = Path(output_path) if output_path is not None else source
    if structure.mode != PptxStructureMode.STRUCTURED or not structure.masters:
        if target != source:
            target.write_bytes(source.read_bytes())
        return target

    layout_name_to_master_id = {
        layout.name: layout.master_id for layout in structure.layouts
    }
    declared_layout_names = {layout.name for layout in structure.layouts}
    master_id_order = [master.id for master in structure.masters]

    with zipfile.ZipFile(source, "r") as zin:
        names = set(zin.namelist())
        files: dict[str, bytes] = {name: zin.read(name) for name in zin.namelist()}

    layout_parts = sorted(
        name
        for name in names
        if re.match(r"^ppt/slideLayouts/slideLayout\d+\.xml$", name)
    )
    if "ppt/slideMasters/slideMaster1.xml" not in names:
        raise ValueError("PPTX has no slideMaster1.xml to clone")

    # Drop layouts that are not in the declared catalog (e.g. PptxGen blank default).
    kept_layouts: list[str] = []
    for layout_part in layout_parts:
        root = ET.fromstring(files[layout_part])
        c_sld = root.find(f"{{{_NS['p']}}}cSld")
        layout_name = c_sld.attrib.get("name", "") if c_sld is not None else ""
        if declared_layout_names and layout_name not in declared_layout_names:
            files.pop(layout_part, None)
            files.pop(_rels_path_for(layout_part), None)
            continue
        kept_layouts.append(layout_part)
    layout_parts = kept_layouts
    if declared_layout_names and not layout_parts:
        raise ValueError(
            "No slide layouts remain after pruning to PresentationStructureSpec names"
        )

    base_master_xml = files["ppt/slideMasters/slideMaster1.xml"]
    master_id_to_part: dict[str, str] = {}
    for index, master_id in enumerate(master_id_order, start=1):
        part = f"ppt/slideMasters/slideMaster{index}.xml"
        master_id_to_part[master_id] = part
        if part not in files:
            files[part] = base_master_xml

    # Map each layout part → master part via cSld/@name.
    layout_to_master_part: dict[str, str] = {}
    master_to_layouts: dict[str, list[str]] = {part: [] for part in master_id_to_part.values()}
    default_master_part = master_id_to_part[master_id_order[0]]

    for layout_part in layout_parts:
        root = ET.fromstring(files[layout_part])
        c_sld = root.find(f"{{{_NS['p']}}}cSld")
        layout_name = c_sld.attrib.get("name", "") if c_sld is not None else ""
        master_id = layout_name_to_master_id.get(layout_name)
        master_part = (
            master_id_to_part.get(master_id, default_master_part)
            if master_id
            else default_master_part
        )
        layout_to_master_part[layout_part] = master_part
        master_to_layouts.setdefault(master_part, []).append(layout_part)

        # Rewrite layout → master relationship.
        rels_part = _rels_path_for(layout_part)
        files[rels_part] = _layout_rels_xml(master_part)

    # Rebuild each master's relationships (layouts + theme).
    for master_part, owned_layouts in master_to_layouts.items():
        files[_rels_path_for(master_part)] = _master_rels_xml(owned_layouts)
        if master_part not in files:
            files[master_part] = base_master_xml

    # Drop unused original master parts beyond our catalog size? Keep only declared.
    for name in list(files):
        match = re.match(r"^ppt/slideMasters/slideMaster(\d+)\.xml$", name)
        if match and int(match.group(1)) > len(master_id_order):
            files.pop(name, None)
            files.pop(_rels_path_for(name), None)

    files["ppt/_rels/presentation.xml.rels"], master_rids = _rewrite_presentation_rels(
        files.get("ppt/_rels/presentation.xml.rels", b""),
        list(master_id_to_part.values()),
    )
    files["ppt/presentation.xml"] = _rewrite_presentation_masters(
        files["ppt/presentation.xml"],
        master_rids=master_rids,
    )
    if "[Content_Types].xml" in files:
        files["[Content_Types].xml"] = _rewrite_content_types(
            files["[Content_Types].xml"],
            list(master_id_to_part.values()),
            layout_parts=layout_parts,
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in sorted(files.items()):
            zout.writestr(name, data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(buffer.getvalue())
    return target


def _rels_path_for(part: str) -> str:
    directory, _, filename = part.rpartition("/")
    return f"{directory}/_rels/{filename}.rels"


def _rel_target(from_part: str, to_part: str) -> str:
    """Build a relative Target from one ppt/ part to another."""
    from_dir = from_part.rsplit("/", 1)[0]
    # Both under ppt/…
    from_bits = from_dir.split("/")
    to_bits = to_part.split("/")
    # Find common prefix
    i = 0
    while i < len(from_bits) and i < len(to_bits) - 1 and from_bits[i] == to_bits[i]:
        i += 1
    up = [".."] * (len(from_bits) - i)
    down = to_bits[i:]
    return "/".join([*up, *down])


def _layout_rels_xml(master_part: str) -> bytes:
    # Layouts live in ppt/slideLayouts/ → master is ../slideMasters/…
    target = _rel_target("ppt/slideLayouts/slideLayout1.xml", master_part)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{_REL_SLIDE_MASTER}" Target="{target}"/>'
        "</Relationships>"
    )
    return xml.encode("utf-8")


def _master_rels_xml(layout_parts: list[str]) -> bytes:
    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    rid = 1
    for layout_part in layout_parts:
        target = _rel_target("ppt/slideMasters/slideMaster1.xml", layout_part)
        parts.append(
            f'<Relationship Id="rId{rid}" Type="{_REL_SLIDE_LAYOUT}" Target="{target}"/>'
        )
        rid += 1
    parts.append(
        f'<Relationship Id="rId{rid}" Type="{_REL_THEME}" Target="../theme/theme1.xml"/>'
    )
    parts.append("</Relationships>")
    return "".join(parts).encode("utf-8")


def _rewrite_presentation_rels(
    original: bytes,
    master_parts: list[str],
) -> tuple[bytes, list[str]]:
    """Return (rels_xml, master_rids) preserving non-master relationships."""
    if not original:
        relationships: list[str] = []
        master_rids: list[str] = []
        rid = 1
        for master_part in master_parts:
            rid_s = f"rId{rid}"
            master_rids.append(rid_s)
            relationships.append(
                f'<Relationship Id="{rid_s}" Type="{_REL_SLIDE_MASTER}" '
                f'Target="{master_part.removeprefix("ppt/")}"/>'
            )
            rid += 1
        body = "".join(relationships)
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{body}</Relationships>"
        ).encode("utf-8")
        return xml, master_rids

    root = ET.fromstring(original)
    for rel in list(root):
        if rel.attrib.get("Type") == _REL_SLIDE_MASTER:
            root.remove(rel)

    used_ids = {
        int(m.group(1))
        for rel in root
        if (m := re.match(r"rId(\d+)$", rel.attrib.get("Id", "")))
    }
    # Prefer reclaiming low rIds starting at 1 for masters (PowerPoint convention).
    next_id = 1
    master_rids: list[str] = []
    insert_at = 0
    for master_part in master_parts:
        while next_id in used_ids:
            next_id += 1
        rid_s = f"rId{next_id}"
        master_rids.append(rid_s)
        used_ids.add(next_id)
        elem = ET.Element(
            f"{{{_NS['pr']}}}Relationship",
            {
                "Id": rid_s,
                "Type": _REL_SLIDE_MASTER,
                "Target": master_part.removeprefix("ppt/"),
            },
        )
        root.insert(insert_at, elem)
        insert_at += 1
        next_id += 1

    return _serialize_xml(root), master_rids


def _rewrite_presentation_masters(
    presentation_xml: bytes,
    *,
    master_rids: list[str],
) -> bytes:
    root = ET.fromstring(presentation_xml)
    lst = root.find(f"{{{_NS['p']}}}sldMasterIdLst")
    if lst is None:
        lst = ET.Element(f"{{{_NS['p']}}}sldMasterIdLst")
        root.insert(0, lst)
    for child in list(lst):
        lst.remove(child)

    base_id = 2147483648
    for index, rid in enumerate(master_rids):
        ET.SubElement(
            lst,
            f"{{{_NS['p']}}}sldMasterId",
            {
                "id": str(base_id + index),
                f"{{{_NS['r']}}}id": rid,
            },
        )
    return _serialize_xml(root)


def _rewrite_content_types(
    content_types_xml: bytes,
    master_parts: list[str],
    *,
    layout_parts: list[str] | None = None,
) -> bytes:
    root = ET.fromstring(content_types_xml)
    kept_parts = {part.lstrip("/") for part in master_parts}
    if layout_parts is not None:
        kept_parts.update(part.lstrip("/") for part in layout_parts)
        # Remove Override entries for pruned slide layouts / masters.
        for node in list(root.findall(f"{{{_NS['ct']}}}Override")):
            part_name = node.attrib.get("PartName", "").lstrip("/")
            if part_name.startswith("ppt/slideLayouts/") and part_name not in kept_parts:
                root.remove(node)
            if part_name.startswith("ppt/slideMasters/") and part_name not in kept_parts:
                root.remove(node)
    existing = {
        node.attrib.get("PartName", "").lstrip("/")
        for node in root.findall(f"{{{_NS['ct']}}}Override")
    }
    for master_part in master_parts:
        part_name = "/" + master_part
        key = master_part
        if key in existing or part_name.lstrip("/") in existing:
            continue
        ET.SubElement(
            root,
            f"{{{_NS['ct']}}}Override",
            {
                "PartName": part_name,
                "ContentType": _CT_SLIDE_MASTER,
            },
        )
    return _serialize_xml(root)


def _serialize_xml(root: ET.Element) -> bytes:
    # Preserve XML declaration.
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return payload
