"""Unit tests for AssetBindingValidator."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from archium.application.visual.asset_binding_validator import AssetBindingValidator
from archium.application.visual.asset_path_resolver import (
    AssetPathResolveContext,
    benchmark_asset_uri,
    project_asset_uri,
)
from archium.domain.studio_errors import (
    STUDIO_ASSET_URI_MISMATCH,
    STUDIO_ASSET_URI_UNSUPPORTED,
    STUDIO_DRAWING_ORIGIN_REQUIRED,
    StudioAssetReferenceError,
)


def test_validate_rejects_malformed_project_uri() -> None:
    asset_id = uuid4()
    validator = AssetBindingValidator()
    with pytest.raises(StudioAssetReferenceError) as exc:
        validator.validate(
            asset_id=asset_id,
            storage_uri="project://site/photo.png",
            asset_origin="project_upload",
            expected_kind="image",
            require_resolvable=False,
        )
    assert exc.value.code == STUDIO_ASSET_URI_UNSUPPORTED


def test_validate_rejects_project_uri_asset_id_mismatch() -> None:
    asset_id = uuid4()
    other_id = uuid4()
    validator = AssetBindingValidator()
    with pytest.raises(StudioAssetReferenceError) as exc:
        validator.validate(
            asset_id=asset_id,
            storage_uri=project_asset_uri(other_id),
            asset_origin="project_upload",
            expected_kind="image",
            require_resolvable=False,
        )
    assert exc.value.code == STUDIO_ASSET_URI_MISMATCH


def test_validate_drawing_requires_project_upload_origin() -> None:
    asset_id = uuid4()
    validator = AssetBindingValidator()
    with pytest.raises(StudioAssetReferenceError) as exc:
        validator.validate(
            asset_id=asset_id,
            storage_uri=project_asset_uri(asset_id),
            asset_origin="reference_case",
            expected_kind="drawing",
            require_resolvable=False,
        )
    assert exc.value.code == STUDIO_DRAWING_ORIGIN_REQUIRED


def _write_min_png(path: Path) -> None:
    from PIL import Image

    Image.new("RGB", (1, 1), color="red").save(path)


def test_validate_resolves_benchmark_uri(tmp_path: Path) -> None:
    asset_id = uuid4()
    case_dir = tmp_path / "case_photo"
    assets = case_dir / "assets"
    assets.mkdir(parents=True)
    asset_file = assets / f"{asset_id}.png"
    _write_min_png(asset_file)
    uri = benchmark_asset_uri("case_photo", f"assets/{asset_id}.png")
    result = AssetBindingValidator().validate(
        asset_id=asset_id,
        storage_uri=uri,
        asset_origin="project_upload",
        expected_kind="image",
        resolve_context=AssetPathResolveContext(
            case_dir=case_dir,
            case_id="case_photo",
            assets_dir=assets,
            benchmark_root=tmp_path,
        ),
    )
    assert result.resolved_path is not None
    assert result.resolved_path.is_file()
