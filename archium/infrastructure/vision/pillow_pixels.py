"""Pillow pixel iteration helpers (get_flattened_data with getdata fallback)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from PIL import Image


def iter_image_pixels(image: Image.Image) -> Iterable[int]:
    """Return flattened pixel values, preferring Pillow 14+ ``get_flattened_data``."""
    flattened = getattr(image, "get_flattened_data", None)
    if flattened is not None:
        return cast(Iterable[int], flattened())
    return cast(Iterable[int], image.getdata())
