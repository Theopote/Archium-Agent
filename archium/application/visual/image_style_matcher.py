"""Deck-level photo style matching — sample stats → ImageUnifyParams.

Not generative. Samples up to N photos, estimates brightness / warmth /
saturation proxies, then nudges shared unify knobs toward a presentation look.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

from archium.domain.visual.image_derivative import (
    ImageUnifyParams,
    default_presentation_unify_params,
)
from archium.logging import get_logger

logger = get_logger(__name__, operation="image_style_matcher")

_TARGET_BRIGHTNESS = 132.0
_TARGET_WARMTH = 0.0  # R−B normalized toward 0 (slight cool deck look handled by bias)
_TARGET_CHROMA = 28.0
_SAMPLE_EDGE = 48


@dataclass(frozen=True)
class PhotoColorStats:
    brightness: float
    warmth: float  # (R − B) / 255, positive = warm
    chroma: float


@dataclass(frozen=True)
class DeckStyleMatchResult:
    unify: ImageUnifyParams
    sample_count: int
    median_brightness: float | None = None
    median_warmth: float | None = None
    median_chroma: float | None = None
    rationale: str = ""


class ImageStyleMatcher:
    """Compute deck-shared ``ImageUnifyParams`` from sampled photo statistics."""

    def match_deck(
        self,
        paths: list[Path],
        *,
        sample_limit: int = 20,
        base: ImageUnifyParams | None = None,
    ) -> DeckStyleMatchResult:
        base_params = base or default_presentation_unify_params()
        samples: list[PhotoColorStats] = []
        for path in paths:
            if len(samples) >= sample_limit:
                break
            stats = self.sample_photo(path)
            if stats is not None:
                samples.append(stats)

        if not samples:
            return DeckStyleMatchResult(
                unify=base_params,
                sample_count=0,
                rationale="no_samples:fallback_base",
            )

        med_b = float(median(item.brightness for item in samples))
        med_w = float(median(item.warmth for item in samples))
        med_c = float(median(item.chroma for item in samples))

        # Brightness: each ~12 luminance points → ~0.04 enhance step.
        brightness = base_params.brightness + (_TARGET_BRIGHTNESS - med_b) / 280.0
        # Warmth: positive warmth → cool the deck (negative temperature).
        temperature = base_params.temperature - med_w * 0.22
        # Chroma: oversaturated phone JPEGs → pull sat down.
        saturation = base_params.saturation + (_TARGET_CHROMA - med_c) / 160.0
        # Soft contrast lift when flat (low chroma + mid brightness).
        contrast = base_params.contrast
        if med_c < 16.0:
            contrast += 0.04
        elif med_c > 40.0:
            contrast -= 0.03

        unify = ImageUnifyParams(
            temperature=_clamp(temperature, -0.25, 0.25),
            saturation=_clamp(saturation, 0.7, 1.25),
            contrast=_clamp(contrast, 0.85, 1.25),
            brightness=_clamp(brightness, 0.85, 1.2),
        )
        rationale = (
            f"deck_sample_n={len(samples)}; "
            f"med_b={med_b:.1f}; med_w={med_w:.3f}; med_c={med_c:.1f}"
        )
        return DeckStyleMatchResult(
            unify=unify,
            sample_count=len(samples),
            median_brightness=med_b,
            median_warmth=med_w,
            median_chroma=med_c,
            rationale=rationale,
        )

    def sample_photo(self, path: Path) -> PhotoColorStats | None:
        if not path.is_file():
            return None
        try:
            from PIL import Image, ImageStat
        except ImportError:
            return None
        try:
            with Image.open(path) as opened:
                rgb = opened.convert("RGB")
                rgb.thumbnail((_SAMPLE_EDGE, _SAMPLE_EDGE))
                gray = rgb.convert("L")
                color = ImageStat.Stat(rgb).mean
                lum = float(ImageStat.Stat(gray).mean[0])
        except OSError as exc:
            logger.info("Style sample failed for %s: %s", path, exc)
            return None
        r, g, b = float(color[0]), float(color[1]), float(color[2])
        warmth = (r - b) / 255.0
        chroma = (abs(r - g) + abs(g - b) + abs(b - r)) / 3.0
        return PhotoColorStats(brightness=lum, warmth=warmth, chroma=chroma)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
