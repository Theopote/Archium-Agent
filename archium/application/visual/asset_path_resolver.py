"""Shim: asset path resolver lives in infrastructure.storage."""

from archium.infrastructure.storage.asset_path_resolver import (
    BENCHMARK_SCHEME,
    PROJECT_SCHEME,
    STORAGE_SCHEME,
    AssetPathResolveContext,
    AssetPathResolver,
    asset_uri_suffix,
    benchmark_asset_uri,
    dump_scene_for_persistence,
    is_machine_absolute_path,
    is_portable_storage_uri,
    iter_scene_asset_uris,
    project_asset_uri,
    resolve_under,
    scene_has_machine_absolute_paths,
    storage_asset_uri,
)

__all__ = [
    "BENCHMARK_SCHEME",
    "PROJECT_SCHEME",
    "STORAGE_SCHEME",
    "AssetPathResolveContext",
    "AssetPathResolver",
    "asset_uri_suffix",
    "benchmark_asset_uri",
    "dump_scene_for_persistence",
    "is_machine_absolute_path",
    "is_portable_storage_uri",
    "iter_scene_asset_uris",
    "project_asset_uri",
    "resolve_under",
    "scene_has_machine_absolute_paths",
    "storage_asset_uri",
]
