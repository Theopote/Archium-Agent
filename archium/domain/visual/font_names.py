"""Shared font family names and fallback chains (domain policy constants)."""

from __future__ import annotations

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
