"""Font resolution provenance for measurement + visual baselines.

Real text metrics use Pillow's FreeType loader (``ImageFont.truetype`` →
``getbbox``). Visual screenshot baselines bind ``font_manifest_hash`` so a CI
image font change fails with an explicit font-drift error instead of a cryptic
pixel diff.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from archium.infrastructure.layout.font_resolver import (
    CJK_FALLBACK_CHAIN,
    DEFAULT_CJK_FONT,
    DEFAULT_LATIN_FONT,
    LATIN_FALLBACK_CHAIN,
    ResolvedFont,
    resolve_font_file,
)

# Families TextMeasurementService / PPTX theme expect by default.
MEASUREMENT_FONT_SPECS: tuple[tuple[str, bool], ...] = (
    (DEFAULT_CJK_FONT, False),
    (DEFAULT_CJK_FONT, True),
    (DEFAULT_LATIN_FONT, False),
    (DEFAULT_LATIN_FONT, True),
)

MEASUREMENT_ENGINE_FREETYPE = "pillow_freetype"
MEASUREMENT_ENGINE_HEURISTIC = "heuristic"


@dataclass(frozen=True)
class FontManifest:
    """Resolved font file used for measurement or render-time fallback."""

    requested_family: str
    resolved_family: str
    source_uri: str | None
    file_hash: str | None
    platform: str
    fallback_used: bool
    bold: bool = False
    measurement_engine: str = MEASUREMENT_ENGINE_FREETYPE

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> FontManifest:
        return cls(
            requested_family=str(payload["requested_family"]),
            resolved_family=str(payload["resolved_family"]),
            source_uri=(
                None
                if payload.get("source_uri") in (None, "")
                else str(payload.get("source_uri"))
            ),
            file_hash=(
                None
                if payload.get("file_hash") in (None, "")
                else str(payload.get("file_hash"))
            ),
            platform=str(payload.get("platform") or platform_key()),
            fallback_used=bool(payload.get("fallback_used")),
            bold=bool(payload.get("bold", False)),
            measurement_engine=str(
                payload.get("measurement_engine") or MEASUREMENT_ENGINE_FREETYPE
            ),
        )


@dataclass(frozen=True)
class FontManifestBundle:
    """Stable set of manifests bound into visual baseline manifests."""

    platform: str
    measurement_engine: str
    fonts: tuple[FontManifest, ...]
    font_manifest_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "platform": self.platform,
            "measurement_engine": self.measurement_engine,
            "font_manifest_hash": self.font_manifest_hash,
            "fonts": [font.to_dict() for font in self.fonts],
        }


def platform_key() -> str:
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _path_to_uri(path: Path) -> str:
    return path.resolve().as_uri()


@lru_cache(maxsize=64)
def _sha256_file(path_str: str) -> str:
    digest = hashlib.sha256()
    with Path(path_str).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_content_hash(resolved: ResolvedFont) -> str:
    digest = _sha256_file(str(resolved.path.resolve()))
    return f"sha256:{digest}:index={resolved.index}"


def _fallback_chain_for(family: str) -> tuple[str, ...]:
    if family in CJK_FALLBACK_CHAIN or family == DEFAULT_CJK_FONT:
        return CJK_FALLBACK_CHAIN
    if family in LATIN_FALLBACK_CHAIN or family == DEFAULT_LATIN_FONT:
        return LATIN_FALLBACK_CHAIN
    # Unknown logical name: try Latin then CJK chains after the request itself.
    return (family, *LATIN_FALLBACK_CHAIN, *CJK_FALLBACK_CHAIN)


def resolve_font_with_policy(
    family: str,
    *,
    bold: bool = False,
) -> tuple[ResolvedFont | None, str, bool]:
    """Resolve a font file, walking shared CJK/Latin fallback chains.

    Returns ``(resolved_file, resolved_family, fallback_used)``.
    """
    requested = (family or "").strip() or DEFAULT_LATIN_FONT
    direct = resolve_font_file(requested, bold=bold)
    if direct is not None:
        return direct, requested, False

    for candidate in _fallback_chain_for(requested):
        if candidate == requested:
            continue
        found = resolve_font_file(candidate, bold=bold)
        if found is not None:
            return found, candidate, True
    return None, requested, True


def build_font_manifest(family: str, *, bold: bool = False) -> FontManifest:
    """Build provenance for one logical family + weight."""
    platform = platform_key()
    resolved, resolved_family, fallback_used = resolve_font_with_policy(family, bold=bold)
    if resolved is None:
        return FontManifest(
            requested_family=family,
            resolved_family=resolved_family,
            source_uri=None,
            file_hash=None,
            platform=platform,
            fallback_used=True,
            bold=bold,
            measurement_engine=MEASUREMENT_ENGINE_HEURISTIC,
        )
    return FontManifest(
        requested_family=family,
        resolved_family=resolved_family,
        source_uri=_path_to_uri(resolved.path),
        file_hash=file_content_hash(resolved),
        platform=platform,
        fallback_used=fallback_used,
        bold=bold,
        measurement_engine=MEASUREMENT_ENGINE_FREETYPE,
    )


def compute_font_manifest_hash(fonts: tuple[FontManifest, ...] | list[FontManifest]) -> str:
    """Stable hash over resolved font identity (not the screenshot pixels)."""
    payload = [
        {
            "requested_family": font.requested_family,
            "resolved_family": font.resolved_family,
            "file_hash": font.file_hash,
            "platform": font.platform,
            "fallback_used": font.fallback_used,
            "bold": font.bold,
            "measurement_engine": font.measurement_engine,
        }
        for font in sorted(
            fonts,
            key=lambda item: (item.requested_family, item.bold, item.resolved_family),
        )
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def build_measurement_font_bundle() -> FontManifestBundle:
    """Default CJK/Latin regular+bold set used by TextMeasurementService."""
    fonts = tuple(
        build_font_manifest(family, bold=bold) for family, bold in MEASUREMENT_FONT_SPECS
    )
    engine = (
        MEASUREMENT_ENGINE_FREETYPE
        if all(font.file_hash for font in fonts)
        else MEASUREMENT_ENGINE_HEURISTIC
    )
    # If any entry fell back to heuristic, mark bundle engine accordingly.
    if any(font.measurement_engine == MEASUREMENT_ENGINE_HEURISTIC for font in fonts):
        engine = MEASUREMENT_ENGINE_HEURISTIC
    return FontManifestBundle(
        platform=platform_key(),
        measurement_engine=engine,
        fonts=fonts,
        font_manifest_hash=compute_font_manifest_hash(fonts),
    )


def compare_font_manifest_binding(
    *,
    baseline_hash: str | None,
    baseline_platform: str | None,
    baseline_fonts: list[dict[str, object]] | None = None,
) -> list[str]:
    """Return issues when a visual baseline's font binding drifts.

    - Missing hash: fail (baselines must bind fonts).
    - Platform mismatch: no issue (hash only enforced on the baseline's OS;
      approve on Linux CI so ``font_platform=linux`` locks CI fonts).
    - Same platform + hash mismatch: fail as font drift (re-approve required).
    """
    del baseline_fonts  # reserved for richer diagnostics in manifests
    issues: list[str] = []
    current = build_measurement_font_bundle()
    if not baseline_hash:
        issues.append(
            "Missing font_manifest_hash — visual baselines must bind CI fonts. "
            "Regenerate candidates and approve-baseline after human review."
        )
        return issues

    if baseline_platform and baseline_platform != current.platform:
        return []

    if baseline_hash != current.font_manifest_hash:
        issues.append(
            "font_manifest_hash mismatch — runtime/CI fonts changed. "
            f"baseline={baseline_hash} host={current.font_manifest_hash}. "
            "This is font drift, not a pure visual regression; "
            "review candidates then approve-baseline."
        )
    return issues


__all__ = [
    "MEASUREMENT_ENGINE_FREETYPE",
    "MEASUREMENT_ENGINE_HEURISTIC",
    "MEASUREMENT_FONT_SPECS",
    "FontManifest",
    "FontManifestBundle",
    "build_font_manifest",
    "build_measurement_font_bundle",
    "compare_font_manifest_binding",
    "compute_font_manifest_hash",
    "file_content_hash",
    "platform_key",
    "resolve_font_with_policy",
]
