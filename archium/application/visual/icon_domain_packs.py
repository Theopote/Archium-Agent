"""Domain icon packs — curated icon sets for common architectural project types."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from archium.application.visual.architectural_icon_registry import (
    ArchitecturalIconRegistry,
    default_icon_pack_root,
)
from archium.domain.visual.architectural_icon import ArchitecturalIcon


@dataclass(frozen=True)
class IconDomainPack:
    """Named set of icon canonical names for a project domain."""

    key: str
    label: str
    icon_names: tuple[str, ...]


def _load_manifest(pack_root: Path | None = None) -> dict[str, object]:
    root = pack_root or default_icon_pack_root()
    payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_icon_domain_packs(pack_root: Path | None = None) -> dict[str, IconDomainPack]:
    """Load domain packs from manifest (e.g. hospital, village)."""
    raw = _load_manifest(pack_root).get("domain_packs")
    if not isinstance(raw, dict):
        return {}
    packs: dict[str, IconDomainPack] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        icons = value.get("icons")
        if not isinstance(icons, list):
            continue
        packs[str(key)] = IconDomainPack(
            key=str(key),
            label=str(value.get("label") or key),
            icon_names=tuple(str(name) for name in icons),
        )
    return packs


def icons_for_domain(
    domain: str,
    *,
    pack_root: Path | None = None,
    registry: ArchitecturalIconRegistry | None = None,
) -> list[ArchitecturalIcon]:
    """Resolve domain pack icon names to registry icons."""
    from archium.application.visual.architectural_icon_registry import (
        load_default_architectural_icon_registry,
    )

    packs = load_icon_domain_packs(pack_root)
    pack = packs.get(domain.strip().casefold())
    if pack is None:
        return []
    reg = registry or load_default_architectural_icon_registry()
    resolved: list[ArchitecturalIcon] = []
    for name in pack.icon_names:
        icon = reg.get_by_name(name)
        if icon is not None:
            resolved.append(icon)
    return resolved


def list_icon_folders(pack_root: Path | None = None) -> tuple[str, ...]:
    """Return declared category folders from manifest."""
    folders = _load_manifest(pack_root).get("folders")
    if isinstance(folders, list):
        return tuple(str(item) for item in folders)
    return ()
