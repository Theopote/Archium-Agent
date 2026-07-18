"""Load project assets as Pillow images."""

from __future__ import annotations

from pathlib import Path

from archium.domain.asset import Asset

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional documents extra
    Image = None  # type: ignore[assignment]


def load_image_from_path(path: str | Path) -> Image.Image:
    if Image is None:
        raise RuntimeError("Pillow is required for visual QA (install archium-agent[documents])")
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"Asset image not found: {resolved}")
    with Image.open(resolved) as opened:
        return opened.convert("RGB")


def load_asset_image(asset: Asset) -> Image.Image:
    return load_image_from_path(asset.path)
