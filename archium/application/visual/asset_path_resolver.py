"""Portable storage URIs for RenderScene assets — resolve only at render time."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.domain.visual.render_scene import (
    ChartNode,
    DrawingNode,
    ImageNode,
    RenderNode,
    RenderScene,
    SceneAssetReference,
)

BENCHMARK_SCHEME = "benchmark://"
PROJECT_SCHEME = "project://"
STORAGE_SCHEME = "storage://"

_WINDOWS_ABS = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_ABS = re.compile(r"^\\\\|^//")


@dataclass(frozen=True)
class AssetPathResolveContext:
    """Runtime roots used to turn a storage URI into a filesystem path."""

    case_dir: Path | None = None
    case_id: str | None = None
    project_id: UUID | str | None = None
    project_storage_root: Path | None = None
    assets_dir: Path | None = None
    project_asset_files: dict[str, Path] = field(default_factory=dict)
    benchmark_root: Path | None = None


def is_portable_storage_uri(value: str) -> bool:
    text = (value or "").strip()
    return text.startswith((BENCHMARK_SCHEME, PROJECT_SCHEME, STORAGE_SCHEME))


def is_machine_absolute_path(value: str) -> bool:
    """Return True for host filesystem absolutes (not portable URIs)."""
    text = (value or "").strip()
    if not text or is_portable_storage_uri(text):
        return False
    if _WINDOWS_ABS.match(text) or _UNC_ABS.match(text):
        return True
    # POSIX absolute paths must count even when evaluated on Windows (CI / Docker).
    if text.startswith("/"):
        return True
    try:
        return Path(text).is_absolute()
    except (OSError, ValueError):
        return False


def benchmark_asset_uri(case_id: str, relative_path: str) -> str:
    rel = relative_path.replace("\\", "/").lstrip("/")
    return f"{BENCHMARK_SCHEME}{case_id}/{rel}"


def project_asset_uri(asset_id: str | UUID) -> str:
    return f"{PROJECT_SCHEME}assets/{asset_id}"


def storage_asset_uri(project_id: str | UUID, relative_path: str) -> str:
    rel = relative_path.replace("\\", "/").lstrip("/")
    return f"{STORAGE_SCHEME}projects/{project_id}/{rel}"


def asset_uri_suffix(storage_uri: str) -> str:
    """Return the file extension for a URI or path (used by format checks)."""
    text = (storage_uri or "").strip().split("?", 1)[0].rstrip("/")
    if "://" in text:
        text = text.split("://", 1)[1]
    name = text.rsplit("/", 1)[-1]
    return Path(name).suffix.lower()


def iter_scene_asset_uris(scene: RenderScene) -> list[str]:
    """Collect persisted asset URI fields from a scene (nodes + manifest + bg)."""
    uris: list[str] = []
    if scene.background.image_asset_path:
        uris.append(scene.background.image_asset_path)
    for node in scene.nodes:
        path = getattr(node, "asset_path", None) or getattr(node, "storage_uri", None)
        if path:
            uris.append(str(path))
    for ref in scene.asset_manifest:
        uri = ref.storage_uri or ref.asset_path
        if uri:
            uris.append(uri)
    return uris


def scene_has_machine_absolute_paths(scene: RenderScene) -> list[str]:
    return [uri for uri in iter_scene_asset_uris(scene) if is_machine_absolute_path(uri)]


class AssetPathResolver:
    """Encode portable storage URIs and resolve them for the current environment."""

    def resolve(
        self,
        storage_uri: str,
        ctx: AssetPathResolveContext | None = None,
    ) -> Path | None:
        text = (storage_uri or "").strip()
        if not text:
            return None
        context = ctx or AssetPathResolveContext()

        if text.startswith(BENCHMARK_SCHEME):
            return self._resolve_benchmark(text[len(BENCHMARK_SCHEME) :], context)
        if text.startswith(PROJECT_SCHEME):
            return self._resolve_project(text[len(PROJECT_SCHEME) :], context)
        if text.startswith(STORAGE_SCHEME):
            return self._resolve_storage(text[len(STORAGE_SCHEME) :], context)

        path = Path(text)
        if path.is_file():
            return path
        if context.case_dir is not None:
            candidate = context.case_dir / text
            if candidate.is_file():
                return candidate
        if context.assets_dir is not None:
            candidate = context.assets_dir / Path(text).name
            if candidate.is_file():
                return candidate
        return path if path.is_absolute() else None

    def portableize(
        self,
        path_or_uri: str,
        ctx: AssetPathResolveContext,
    ) -> str:
        """Convert a filesystem path into a portable URI when possible."""
        text = (path_or_uri or "").strip()
        if not text:
            return text
        if is_portable_storage_uri(text):
            return text.replace("\\", "/")

        path = Path(text)
        case_id = ctx.case_id
        case_dir = ctx.case_dir
        if case_dir is not None:
            case_id = case_id or case_dir.name
            try:
                relative = path.resolve().relative_to(case_dir.resolve())
                return benchmark_asset_uri(case_id, relative.as_posix())
            except (OSError, ValueError):
                pass
            # Match by case folder segment + assets filename (cross-machine rewrite).
            parts = path.as_posix().split("/")
            if case_id in parts:
                idx = parts.index(case_id)
                tail = "/".join(parts[idx + 1 :])
                if tail:
                    return benchmark_asset_uri(case_id, tail)
            if ctx.assets_dir is not None and path.name:
                asset_file = ctx.assets_dir / path.name
                if asset_file.is_file():
                    return benchmark_asset_uri(case_id or case_dir.name, f"assets/{path.name}")

        project_id = str(ctx.project_id) if ctx.project_id else None
        root = ctx.project_storage_root
        if project_id and root is not None:
            try:
                relative = path.resolve().relative_to((root / project_id).resolve())
                return storage_asset_uri(project_id, relative.as_posix())
            except (OSError, ValueError):
                pass

        # Last resort: relative path under assets_dir by basename.
        if case_id and path.name:
            return benchmark_asset_uri(case_id, f"assets/{path.name}")
        return text.replace("\\", "/")

    def resolve_scene(
        self,
        scene: RenderScene,
        ctx: AssetPathResolveContext,
    ) -> RenderScene:
        """Return a copy with asset_path fields resolved to absolute filesystem paths.

        The returned scene is for renderers only — do not persist it.
        """
        nodes: list[RenderNode] = []
        for node in scene.nodes:
            if isinstance(node, (ImageNode, DrawingNode)):
                uri = node.storage_uri or node.asset_path
                resolved = self.resolve(uri, ctx) if uri else None
                absolute = str(resolved) if resolved is not None else (node.asset_path or "")
                nodes.append(
                    node.model_copy(
                        update={
                            "asset_path": absolute,
                            "resolved_path": absolute if resolved is not None else None,
                        }
                    )
                )
            elif isinstance(node, ChartNode) and node.preview_storage_uri:
                resolved = self.resolve(node.preview_storage_uri, ctx)
                nodes.append(
                    node.model_copy(
                        update={
                            "preview_resolved_path": (
                                str(resolved) if resolved is not None else None
                            ),
                        }
                    )
                )
            else:
                nodes.append(node)

        manifest: list[SceneAssetReference] = []
        for ref in scene.asset_manifest:
            uri = ref.storage_uri or ref.asset_path
            resolved = self.resolve(uri, ctx) if uri else None
            absolute = str(resolved) if resolved is not None else (ref.asset_path or uri)
            manifest.append(
                ref.model_copy(
                    update={
                        "storage_uri": uri,
                        "asset_path": absolute,
                        "resolved_path": absolute if resolved is not None else None,
                    }
                )
            )

        background = scene.background
        if background.image_asset_path:
            resolved_bg = self.resolve(background.image_asset_path, ctx)
            if resolved_bg is not None:
                background = background.model_copy(
                    update={"image_asset_path": str(resolved_bg)}
                )

        return scene.model_copy(
            update={
                "nodes": nodes,
                "asset_manifest": manifest,
                "background": background,
            }
        )

    def portableize_scene(
        self,
        scene: RenderScene,
        ctx: AssetPathResolveContext,
    ) -> RenderScene:
        """Rewrite absolute asset paths in a scene to portable storage URIs."""
        nodes: list[RenderNode] = []
        for node in scene.nodes:
            if isinstance(node, (ImageNode, DrawingNode)):
                raw = node.storage_uri or node.asset_path
                uri = self.portableize(raw, ctx) if raw else ""
                nodes.append(
                    node.model_copy(
                        update={
                            "storage_uri": uri,
                            "asset_path": uri,
                            "resolved_path": None,
                        }
                    )
                )
            else:
                nodes.append(node)

        manifest: list[SceneAssetReference] = []
        for ref in scene.asset_manifest:
            raw = ref.storage_uri or ref.asset_path
            uri = self.portableize(raw, ctx) if raw else ""
            manifest.append(
                ref.model_copy(
                    update={
                        "storage_uri": uri,
                        "asset_path": uri,
                        "resolved_path": None,
                    }
                )
            )

        background = scene.background
        if background.image_asset_path:
            background = background.model_copy(
                update={
                    "image_asset_path": self.portableize(background.image_asset_path, ctx)
                }
            )

        return scene.model_copy(
            update={
                "nodes": nodes,
                "asset_manifest": manifest,
                "background": background,
            }
        )

    def _resolve_benchmark(self, remainder: str, ctx: AssetPathResolveContext) -> Path | None:
        parts = remainder.replace("\\", "/").split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None
        case_id, relative = parts[0], parts[1]
        if ctx.case_dir is not None and (ctx.case_id is None or ctx.case_id == case_id):
            candidate = ctx.case_dir / relative
            if candidate.is_file():
                return candidate
        if ctx.benchmark_root is not None:
            candidate = ctx.benchmark_root / case_id / relative
            if candidate.is_file():
                return candidate
        if ctx.assets_dir is not None:
            candidate = ctx.assets_dir / Path(relative).name
            if candidate.is_file():
                return candidate
        return None

    def _resolve_project(self, remainder: str, ctx: AssetPathResolveContext) -> Path | None:
        # project://assets/<asset-id>[/<filename>]
        parts = remainder.replace("\\", "/").strip("/").split("/")
        if not parts or parts[0] != "assets" or len(parts) < 2:
            return None
        asset_id = parts[1]
        mapped = ctx.project_asset_files.get(asset_id)
        if mapped is not None and mapped.is_file():
            return mapped
        if ctx.project_id and ctx.project_storage_root is not None:
            # Fallback: look under project root by asset id filename patterns.
            root = ctx.project_storage_root / str(ctx.project_id)
            if len(parts) >= 3:
                candidate = root / "/".join(parts[2:])
                if candidate.is_file():
                    return candidate
            for pattern in (f"{asset_id}.*", f"**/{asset_id}.*"):
                matches = list(root.glob(pattern)) if root.is_dir() else []
                if matches:
                    return matches[0]
        return None

    def _resolve_storage(self, remainder: str, ctx: AssetPathResolveContext) -> Path | None:
        # storage://projects/<project-id>/<relative-path>
        parts = remainder.replace("\\", "/").strip("/").split("/", 2)
        if len(parts) < 3 or parts[0] != "projects":
            return None
        project_id, relative = parts[1], parts[2]
        if ctx.project_storage_root is None:
            return None
        candidate = ctx.project_storage_root / project_id / relative
        return candidate if candidate.is_file() else candidate


def dump_scene_for_persistence(scene: RenderScene) -> dict[str, Any]:
    """Serialize a scene for disk without runtime-only resolved_path fields."""
    return scene.model_dump(mode="json", exclude_none=False)
