"""Resolve DesignSystem font families to loadable TrueType / OpenType files."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol, cast

try:
    from PIL import ImageFont
except ImportError:  # pragma: no cover - optional until documents/full extra installed
    ImageFont = None  # type: ignore[assignment]

_FONT_ROOT = Path(__file__).resolve().parent / "fonts"

# Shared with scene_fonts / FontManifest — keep names identical for PPTX + measurement.
DEFAULT_CJK_FONT = "Microsoft YaHei"
DEFAULT_LATIN_FONT = "Arial"
CJK_FALLBACK_CHAIN: tuple[str, ...] = (
    DEFAULT_CJK_FONT,
    "PingFang SC",
    "Noto Sans SC",
    "Source Han Sans SC",
    "SimHei",
    "WenQuanYi Micro Hei",
)
LATIN_FALLBACK_CHAIN: tuple[str, ...] = (
    DEFAULT_LATIN_FONT,
    "Helvetica",
    "Liberation Sans",
    "DejaVu Sans",
)


class TruetypeFont(Protocol):
    def getbbox(self, text: str, /, *args: object, **kwargs: object) -> tuple[int, int, int, int]: ...

# Logical family name → platform candidate paths (path, collection index).
_FONT_CANDIDATES: dict[str, dict[str, list[tuple[str, int]]]] = {
    "Microsoft YaHei": {
        "win32": [
            (r"C:\Windows\Fonts\msyh.ttc", 0),
            (r"C:\Windows\Fonts\msyhbd.ttc", 0),
        ],
        "linux": [
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
            ("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
        ],
        "darwin": [
            ("/System/Library/Fonts/PingFang.ttc", 0),
            ("/System/Library/Fonts/STHeiti Light.ttc", 0),
        ],
    },
    "Arial": {
        "win32": [
            (r"C:\Windows\Fonts\arial.ttf", 0),
            (r"C:\Windows\Fonts\ARIAL.TTF", 0),
        ],
        "linux": [
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
        ],
        "darwin": [
            ("/Library/Fonts/Arial.ttf", 0),
            ("/System/Library/Fonts/Supplemental/Arial.ttf", 0),
        ],
    },
}

_BOLD_SUFFIX_CANDIDATES: dict[str, dict[str, list[tuple[str, int]]]] = {
    "Microsoft YaHei": {
        "win32": [(r"C:\Windows\Fonts\msyhbd.ttc", 0)],
        "linux": [
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 0),
        ],
        "darwin": [
            ("/System/Library/Fonts/PingFang.ttc", 1),
        ],
    },
    "Arial": {
        "win32": [(r"C:\Windows\Fonts\arialbd.ttf", 0)],
        "linux": [
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ],
        "darwin": [
            ("/Library/Fonts/Arial Bold.ttf", 0),
            ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
        ],
    },
}


@dataclass(frozen=True)
class ResolvedFont:
    path: Path
    index: int = 0


def _platform_key() -> str:
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _bundled_font_paths(family: str, *, bold: bool) -> list[ResolvedFont]:
    slug = family.lower().replace(" ", "-")
    suffix = "bold" if bold else "regular"
    candidates = [
        _FONT_ROOT / f"{slug}-{suffix}.ttf",
        _FONT_ROOT / f"{slug}-{suffix}.otf",
        _FONT_ROOT / f"{slug}-{suffix}.ttc",
    ]
    return [ResolvedFont(path=path) for path in candidates if path.is_file()]


def _platform_candidates(family: str, *, bold: bool) -> list[ResolvedFont]:
    table = _BOLD_SUFFIX_CANDIDATES if bold else _FONT_CANDIDATES
    entries = table.get(family, {}).get(_platform_key(), [])
    if bold and not entries:
        entries = _FONT_CANDIDATES.get(family, {}).get(_platform_key(), [])
    return [ResolvedFont(path=Path(raw), index=index) for raw, index in entries]


def resolve_font_file(family: str, *, bold: bool = False) -> ResolvedFont | None:
    """Return the first loadable font file for a logical family name."""
    for candidate in (*_bundled_font_paths(family, bold=bold), *_platform_candidates(family, bold=bold)):
        if candidate.path.is_file():
            return candidate
    return None


@lru_cache(maxsize=64)
def load_truetype_font(family: str, *, bold: bool, size_px: int) -> TruetypeFont | None:
    """Load a PIL FreeTypeFont for ``family`` at ``size_px``, or None when unavailable.

    Uses Pillow's FreeType backend (``ImageFont.truetype``). When the requested
    logical family has no file, walks the shared CJK/Latin fallback chain from
    ``font_manifest.resolve_font_with_policy``.
    """
    if ImageFont is None or size_px <= 0:
        return None
    # Local import avoids cycle: font_manifest → font_resolver.
    from archium.infrastructure.layout.font_manifest import resolve_font_with_policy

    resolved, _resolved_family, _fallback_used = resolve_font_with_policy(family, bold=bold)
    if resolved is None:
        return None
    try:
        loaded = ImageFont.truetype(str(resolved.path), size_px, index=resolved.index)
        return cast(TruetypeFont, loaded)
    except OSError:
        return None


def fonts_available() -> bool:
    """True when at least the default CJK + Latin families resolve on this machine."""
    if ImageFont is None:
        return False
    return (
        load_truetype_font("Microsoft YaHei", bold=False, size_px=16) is not None
        and load_truetype_font("Arial", bold=False, size_px=16) is not None
    )
