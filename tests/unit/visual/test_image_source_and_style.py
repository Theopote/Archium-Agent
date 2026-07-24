"""Unit tests for image source classification and deck style matching."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.visual.image_source_classifier import ImageSourceClassifier
from archium.application.visual.image_style_matcher import ImageStyleMatcher
from archium.application.visual.image_treatment_spec_planner import ImageTreatmentSpecPlanner
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.image_derivative import (
    ImageSourceKind,
    ImageTreatmentMode,
    ImageUnifyParams,
    default_presentation_unify_params,
)
from archium.domain.visual.render_scene import ImageNode
from PIL import Image


def test_classify_wechat_export_by_filename() -> None:
    result = ImageSourceClassifier().classify(filename="mmexport1712345678901.jpg")
    assert result.kind == ImageSourceKind.WECHAT_EXPORT
    assert result.confidence >= 0.9


def test_classify_scan_and_historic_tags() -> None:
    scan = ImageSourceClassifier().classify(filename="page.png", tags=["扫描"])
    assert scan.kind == ImageSourceKind.DOCUMENT_SCAN
    historic = ImageSourceClassifier().classify(
        filename="courtyard.jpg",
        description="历史院区老照片",
        tags=["历史"],
    )
    assert historic.kind == ImageSourceKind.HISTORICAL


def test_classify_site_photo_from_description() -> None:
    result = ImageSourceClassifier().classify(
        filename="DSC0001.jpg",
        description="现场踏勘入口广场",
        tags=["现场"],
    )
    assert result.kind == ImageSourceKind.SITE_PHOTO


def test_style_matcher_cools_warm_batch(tmp_path: Path) -> None:
    paths: list[Path] = []
    for index in range(5):
        path = tmp_path / f"warm_{index}.jpg"
        # Warm orange-ish phone look.
        Image.new("RGB", (200, 150), color=(210, 140, 90)).save(path, format="JPEG")
        paths.append(path)

    matched = ImageStyleMatcher().match_deck(paths, base=default_presentation_unify_params())
    assert matched.sample_count == 5
    assert matched.median_warmth is not None and matched.median_warmth > 0
    # Warm batch should push temperature cooler than base (more negative or less positive).
    assert matched.unify.temperature <= default_presentation_unify_params().temperature


def test_style_matcher_brightens_dark_batch(tmp_path: Path) -> None:
    paths: list[Path] = []
    for index in range(4):
        path = tmp_path / f"dark_{index}.jpg"
        Image.new("RGB", (200, 150), color=(40, 42, 45)).save(path, format="JPEG")
        paths.append(path)
    base = ImageUnifyParams(brightness=1.0, saturation=1.0, contrast=1.0, temperature=0.0)
    matched = ImageStyleMatcher().match_deck(paths, base=base)
    assert matched.unify.brightness > base.brightness


def test_planner_uses_deck_unify_and_source_kind() -> None:
    design = default_presentation_design_system()
    design = design.model_copy(
        update={
            "image_style": design.image_style.model_copy(
                update={"photo_treatment": PhotoTreatment.SUBTLE_UNIFY}
            )
        }
    )
    deck = ImageUnifyParams(temperature=-0.12, saturation=0.85, contrast=1.1, brightness=1.05)
    node = ImageNode(
        id="historic_photo",
        x=0,
        y=0,
        width=2,
        height=2,
        z_index=1,
        asset_id=uuid4(),
        storage_uri="project://assets/x",
        asset_origin="project_upload",
        semantic_role="historic_photo",
    )
    asset = Asset(
        id=node.asset_id or uuid4(),
        project_id=uuid4(),
        filename="mmexport123.jpg",
        path="/tmp/x.jpg",
        asset_type=AssetType.PHOTO,
        tags=["微信"],
        description="院区照片",
    )
    spec = ImageTreatmentSpecPlanner().plan_for_node(
        node,
        design_system=design,
        asset=asset,
        source_kind=ImageSourceKind.WECHAT_EXPORT,
        deck_unify=deck,
    )
    assert spec is not None
    assert spec.mode == ImageTreatmentMode.PRESENTATION_UNIFY
    assert spec.source_kind == ImageSourceKind.WECHAT_EXPORT
    assert spec.unify.temperature == pytest.approx(-0.12)
    assert "deck_style_match" in spec.rationale
    assert spec.crop_strategy.value != "none"


def test_planner_scan_source_forces_document_scan_mode() -> None:
    design = default_presentation_design_system()
    design = design.model_copy(
        update={
            "image_style": design.image_style.model_copy(
                update={"photo_treatment": PhotoTreatment.SUBTLE_UNIFY}
            )
        }
    )
    node = ImageNode(
        id="scan",
        x=0,
        y=0,
        width=2,
        height=2,
        z_index=1,
        asset_id=uuid4(),
        storage_uri="project://assets/scan",
        asset_origin="project_upload",
    )
    spec = ImageTreatmentSpecPlanner().plan_for_node(
        node,
        design_system=design,
        source_kind=ImageSourceKind.DOCUMENT_SCAN,
    )
    assert spec is not None
    assert spec.mode == ImageTreatmentMode.DOCUMENT_SCAN
    assert spec.enhance.denoise is True
