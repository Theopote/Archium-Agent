"""Architecture doc ↔ domain contract tests.

Parses machine-readable ``arch-contract:*`` fences in
``docs/architecture/current-system.md`` and asserts they match live enums and
policy helpers. Keeps the architecture doc from drifting into aspirational text.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from archium.domain.visual.element_comment import ElementCommentScope
from archium.domain.visual.enums import OverflowPolicy
from archium.domain.visual.image_derivative import (
    ImageAssetClass,
    ImageDerivative,
    ImageTreatmentMode,
    ImageTreatmentSpec,
    mode_allowed_for_asset_class,
)
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.slide_capacity_budget import CapacityStatus
from archium.ui.product_flow import primary_stages

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_ARCH_DOC = _ROOT / "docs" / "architecture" / "current-system.md"
_CANVAS_TSX = (
    _ROOT
    / "archium"
    / "ui"
    / "components"
    / "canvas_editor"
    / "frontend"
    / "src"
    / "CanvasEditor.tsx"
)
_BRIDGE_PY = _ROOT / "archium" / "ui" / "studio" / "canvas_command_bridge.py"

_FENCE_RE = re.compile(
    r"```arch-contract:(?P<name>[a-z0-9-]+)\n(?P<body>.*?)\n```",
    re.S,
)


def _load_contracts() -> dict[str, list[str]]:
    text = _ARCH_DOC.read_text(encoding="utf-8")
    contracts: dict[str, list[str]] = {}
    for match in _FENCE_RE.finditer(text):
        values = [
            line.strip()
            for line in match.group("body").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        contracts[match.group("name")] = values
    assert contracts, "expected arch-contract fences in current-system.md"
    return contracts


@pytest.fixture(scope="module")
def contracts() -> dict[str, list[str]]:
    return _load_contracts()


def test_documented_capacity_statuses_match_enum(contracts: dict[str, list[str]]) -> None:
    documented = set(contracts["capacity-status"])
    actual = {item.value for item in CapacityStatus}
    assert documented == actual
    # Prose still lists the four statuses inline.
    prose = _ARCH_DOC.read_text(encoding="utf-8")
    for status in sorted(actual):
        assert f"`{status}`" in prose or status in prose


def test_documented_comment_scopes_match_domain_enum(
    contracts: dict[str, list[str]],
) -> None:
    documented = set(contracts["element-comment-scope"])
    actual = {item.value for item in ElementCommentScope}
    assert documented == actual


def test_documented_image_treatment_modes_match_enum(
    contracts: dict[str, list[str]],
) -> None:
    documented = set(contracts["image-treatment-mode"])
    actual = {item.value for item in ImageTreatmentMode}
    assert documented == actual


def test_evidence_image_policy_disallows_artistic_treatment(
    contracts: dict[str, list[str]],
) -> None:
    evidence_classes = {ImageAssetClass(value) for value in contracts["evidence-asset-class"]}
    allowed = {ImageTreatmentMode(value) for value in contracts["evidence-allowed-modes"]}
    assert evidence_classes == {
        ImageAssetClass.PROJECT_DRAWING,
        ImageAssetClass.PROJECT_EVIDENCE_PHOTO,
    }
    assert allowed == {ImageTreatmentMode.NONE, ImageTreatmentMode.SAFE_NORMALIZE}

    for asset_class in evidence_classes:
        for mode in ImageTreatmentMode:
            expected = mode in allowed
            assert mode_allowed_for_asset_class(asset_class, mode) is expected, (
                f"{asset_class.value} + {mode.value}"
            )
        assert not mode_allowed_for_asset_class(
            asset_class,
            ImageTreatmentMode.PRESENTATION_UNIFY,
        )


def test_image_derivative_contract_is_immutable_sidecar() -> None:
    fields = set(ImageDerivative.model_fields)
    assert "original_asset_id" in fields
    assert "treatment_spec_id" in fields
    assert "params_hash" in fields
    assert "storage_uri" in fields
    # Spec plans treatment; derivative never replaces the original asset id field set.
    assert "original_asset_id" in ImageTreatmentSpec.model_fields


def test_documented_overflow_policy_default_matches_layout_plan(
    contracts: dict[str, list[str]],
) -> None:
    assert contracts["overflow-policy-default"] == [OverflowPolicy.WARN.value]
    assert LayoutPlan.model_fields["overflow_policy"].default == OverflowPolicy.WARN


def test_documented_geometry_authority_values(
    contracts: dict[str, list[str]],
) -> None:
    from uuid import uuid4

    from archium.domain.visual.enums import LayoutFamily

    documented = set(contracts["geometry-authority"])
    assert documented == {"layout_plan", "render_scene"}
    assert LayoutPlan.model_fields["geometry_authority"].default == "layout_plan"
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="centered",
        page_width=10,
        page_height=5.625,
        whitespace_ratio=0.4,
        elements=[],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    scene_owned = plan.with_scene_geometry_authority(3)
    assert scene_owned.geometry_authority == "render_scene"
    assert scene_owned.synced_scene_version == 3
    layout_owned = scene_owned.with_layout_geometry_authority()
    assert layout_owned.geometry_authority == "layout_plan"
    assert layout_owned.synced_scene_version is None


def test_documented_formal_export_authority_is_render_scene(
    contracts: dict[str, list[str]],
) -> None:
    from archium.domain.export_authority import (
        FORMAL_EDITABLE_PPTX_AUTHORITY,
        FormalExportAuthority,
        is_formal_editable_pptx_authority,
    )

    assert contracts["formal-export-authority"] == [FormalExportAuthority.RENDER_SCENE.value]
    assert FORMAL_EDITABLE_PPTX_AUTHORITY == FormalExportAuthority.RENDER_SCENE
    assert is_formal_editable_pptx_authority("render_scene")
    assert not is_formal_editable_pptx_authority("presentation_spec")
    prose = _ARCH_DOC.read_text(encoding="utf-8")
    assert "DOM-003" in prose
    assert "PresentationSpec" in prose


def test_documented_legacy_spec_pptx_fallback_default_is_false(
    contracts: dict[str, list[str]],
) -> None:
    from archium.config.settings import Settings

    assert contracts["legacy-spec-pptx-fallback-default"] == ["false"]
    assert Settings().allow_legacy_presentation_spec_pptx_fallback is False


def test_formal_export_call_sites_do_not_force_legacy_spec_fallback() -> None:
    """Delivery paths must not opt into Spec PPTX unless settings explicitly allow."""
    roots = (
        _ROOT / "archium" / "workflow" / "nodes" / "export.py",
        _ROOT / "archium" / "application" / "export_service.py",
        _ROOT / "archium" / "ui" / "workspace_service.py",
    )
    for path in roots:
        source = path.read_text(encoding="utf-8")
        assert "allow_legacy_spec_fallback=True" not in source, path.name


def test_documented_canvas_capabilities_exist_in_runtime(
    contracts: dict[str, list[str]],
) -> None:
    required = set(contracts["canvas-capabilities"])
    canvas = _CANVAS_TSX.read_text(encoding="utf-8")
    bridge = _BRIDGE_PY.read_text(encoding="utf-8")
    assert "marquee" in required and "marquee" in canvas
    assert "shiftKey" in required and "shiftKey" in canvas
    assert "set_studio_selection" in required
    assert "def set_studio_selection" in bridge


def test_documented_product_flow_stages_match_primary_stages(
    contracts: dict[str, list[str]],
) -> None:
    documented = contracts["product-flow-stages"]
    actual = [stage.id for stage in primary_stages()]
    assert documented == actual
