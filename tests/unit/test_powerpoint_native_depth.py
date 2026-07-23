"""Honest PowerPoint native-depth inventory — map ≠ depth."""

from __future__ import annotations

from pathlib import Path

from archium.domain.powerpoint_capability import (
    FORBIDDEN_NATIVE_DEPTH_CLAIMS,
    POWERPOINT_NATIVE_DEPTH_INVENTORY,
    PowerPointDepthStatus,
    claim_implies_forbidden_native_depth,
    depth_entries_by_status,
    depth_entry,
    native_depth_is_shallow,
)


def test_depth_inventory_marks_core_gaps_not_implemented() -> None:
    for construct_id in (
        "connector",
        "preset_shape",
        "freeform_path",
        "group",
        "gradient_fill",
        "pattern_fill",
        "shadow_effect",
        "glow_effect",
        "picture_shape_crop",
        "transition",
    ):
        assert depth_entry(construct_id).status is PowerPointDepthStatus.NOT_IMPLEMENTED


def test_depth_inventory_marks_partial_chart_table_master() -> None:
    assert depth_entry("native_chart").status is PowerPointDepthStatus.PARTIAL
    assert depth_entry("native_table").status is PowerPointDepthStatus.PARTIAL
    assert depth_entry("master_layout").status is PowerPointDepthStatus.PARTIAL
    assert depth_entry("basic_shape").status is PowerPointDepthStatus.PARTIAL


def test_native_depth_is_currently_shallow() -> None:
    assert native_depth_is_shallow()
    not_implemented = depth_entries_by_status(PowerPointDepthStatus.NOT_IMPLEMENTED)
    implemented = depth_entries_by_status(PowerPointDepthStatus.IMPLEMENTED)
    assert len(not_implemented) >= len(implemented)
    assert len(POWERPOINT_NATIVE_DEPTH_INVENTORY) >= 15


def test_forbidden_native_depth_claims_are_detected() -> None:
    assert claim_implies_forbidden_native_depth("我们做到了深度原生 PowerPoint")
    assert claim_implies_forbidden_native_depth("This is deep native PowerPoint")
    assert not claim_implies_forbidden_native_depth("支持范围内可编辑的文本与图片")
    assert "深度原生 PowerPoint" in FORBIDDEN_NATIVE_DEPTH_CLAIMS


def test_capability_contract_docs_forbid_deep_native_claim() -> None:
    contract = Path("docs/architecture/powerpoint-capability-contract.md").read_text(
        encoding="utf-8"
    )
    assert "Native depth inventory" in contract
    assert "most of the map is still empty" in contract
    assert "深度原生 PowerPoint" in contract
    assert "Do **not** describe Archium as" in contract
