"""Tests for portable asset path resolver and scene URI policy."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.asset_path_resolver import (
    AssetPathResolveContext,
    AssetPathResolver,
    benchmark_asset_uri,
    is_machine_absolute_path,
    is_portable_storage_uri,
    project_asset_uri,
    scene_has_machine_absolute_paths,
    storage_asset_uri,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    ImageNode,
    RenderScene,
    SceneAssetReference,
    compute_scene_hash,
)


def test_portable_uri_helpers() -> None:
    assert is_portable_storage_uri("benchmark://case_002/assets/a.png")
    assert is_portable_storage_uri(project_asset_uri(uuid4()))
    assert is_portable_storage_uri(storage_asset_uri(uuid4(), "uploads/a.png"))
    assert not is_portable_storage_uri(r"C:\Users\navib\file.png")
    assert is_machine_absolute_path(r"C:\Users\navib\file.png")
    assert is_machine_absolute_path("/tmp/file.png")
    assert not is_machine_absolute_path("benchmark://case_001/assets/a.png")


def test_benchmark_uri_roundtrip(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_002_site_photos"
    assets = case_dir / "assets"
    assets.mkdir(parents=True)
    asset = assets / "photo.png"
    asset.write_bytes(b"png")
    uri = benchmark_asset_uri("case_002_site_photos", "assets/photo.png")
    resolved = AssetPathResolver().resolve(
        uri,
        AssetPathResolveContext(
            case_dir=case_dir,
            case_id="case_002_site_photos",
            assets_dir=assets,
            benchmark_root=tmp_path,
        ),
    )
    assert resolved is not None
    assert resolved.is_file()
    assert resolved.resolve() == asset.resolve()


def test_portableize_rewrites_windows_absolute(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_002_site_photos"
    assets = case_dir / "assets"
    assets.mkdir(parents=True)
    asset = assets / "c002.png"
    asset.write_bytes(b"png")
    fake_abs = Path(r"C:\Users\navib\Desktop\development\Archium-Agent") / (
        "tests/benchmark/architectural_slides/case_002_site_photos/assets/c002.png"
    )
    uri = AssetPathResolver().portableize(
        str(fake_abs),
        AssetPathResolveContext(
            case_dir=case_dir,
            case_id="case_002_site_photos",
            assets_dir=assets,
        ),
    )
    assert uri == "benchmark://case_002_site_photos/assets/c002.png"


def test_portableize_scene_excludes_absolute_from_hash(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_001_site_plan"
    assets = case_dir / "assets"
    assets.mkdir(parents=True)
    asset = assets / "plan.png"
    asset.write_bytes(b"png")
    absolute = str(asset.resolve())
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="hero",
                x=0,
                y=0,
                width=4,
                height=3,
                asset_path=absolute,
            )
        ],
        asset_manifest=[SceneAssetReference(asset_path=absolute)],
    )
    assert scene_has_machine_absolute_paths(scene)
    portable = AssetPathResolver().portableize_scene(
        scene,
        AssetPathResolveContext(
            case_dir=case_dir,
            case_id=case_dir.name,
            assets_dir=assets,
        ),
    )
    assert not scene_has_machine_absolute_paths(portable)
    assert portable.nodes[0].asset_path.startswith("benchmark://")
    assert portable.asset_manifest[0].storage_uri.startswith("benchmark://")
    # Hash must be stable across machines (no absolute path bytes).
    assert "C:" not in portable.scene_hash_input()
    assert "\\" not in portable.nodes[0].asset_path
    digest = compute_scene_hash(portable)
    assert len(digest) == 64
