"""FontManifest provenance and FreeType measurement binding."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.visual.scene_fonts import DEFAULT_CJK_FONT, DEFAULT_LATIN_FONT
from archium.domain.visual import default_presentation_design_system
from archium.infrastructure.layout.font_manifest import (
    MEASUREMENT_ENGINE_FREETYPE,
    FontManifest,
    build_font_manifest,
    build_measurement_font_bundle,
    compare_font_manifest_binding,
    compute_font_manifest_hash,
    platform_key,
    resolve_font_with_policy,
)
from archium.infrastructure.layout.font_resolver import fonts_available
from archium.infrastructure.layout.text_measurement import TextMeasurementService
from archium.infrastructure.renderers.pptxgen.design_token_adapter import (
    design_system_to_pptx_theme,
)


@pytest.mark.unit
def test_font_manifest_uses_freetype_files() -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    bundle = build_measurement_font_bundle()
    assert bundle.platform == platform_key()
    assert bundle.measurement_engine == MEASUREMENT_ENGINE_FREETYPE
    assert bundle.font_manifest_hash.startswith("sha256:")
    assert len(bundle.fonts) == 4
    for font in bundle.fonts:
        assert font.source_uri
        assert font.file_hash and font.file_hash.startswith("sha256:")
        assert font.measurement_engine == MEASUREMENT_ENGINE_FREETYPE


@pytest.mark.unit
def test_fallback_when_family_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from archium.infrastructure.layout import font_manifest as fm
    from archium.infrastructure.layout import font_resolver as fr

    empty_root = tmp_path / "fonts"
    empty_root.mkdir()
    monkeypatch.setattr(fr, "_FONT_ROOT", empty_root)
    monkeypatch.setattr(fr, "_FONT_CANDIDATES", {})
    monkeypatch.setattr(fr, "_BOLD_SUFFIX_CANDIDATES", {})
    fr.load_truetype_font.cache_clear()

    resolved, resolved_family, fallback_used = resolve_font_with_policy(
        "MissingFamilyXYZ", bold=False
    )
    assert resolved is None
    assert resolved_family == "MissingFamilyXYZ"
    assert fallback_used
    # Ensure the policy walked fallbacks instead of short-circuiting on a system font.
    assert fm.resolve_font_file("Arial", bold=False) is None


@pytest.mark.unit
def test_compare_binding_detects_hash_drift() -> None:
    issues = compare_font_manifest_binding(
        baseline_hash="sha256:deadbeef",
        baseline_platform=platform_key(),
    )
    assert any(item.startswith("font_manifest_hash mismatch") for item in issues)


@pytest.mark.unit
def test_compare_binding_skips_cross_platform() -> None:
    other = "linux" if platform_key() != "linux" else "win32"
    issues = compare_font_manifest_binding(
        baseline_hash="sha256:deadbeef",
        baseline_platform=other,
    )
    assert issues == []


@pytest.mark.unit
def test_compare_binding_requires_hash() -> None:
    issues = compare_font_manifest_binding(baseline_hash=None, baseline_platform=None)
    assert any(item.startswith("Missing font_manifest_hash") for item in issues)


@pytest.mark.unit
def test_hash_stable_for_same_manifests() -> None:
    fonts = (
        FontManifest(
            requested_family="Arial",
            resolved_family="Arial",
            source_uri="file:///tmp/a.ttf",
            file_hash="sha256:abc:index=0",
            platform="linux",
            fallback_used=False,
            bold=False,
        ),
        FontManifest(
            requested_family="Arial",
            resolved_family="Arial",
            source_uri="file:///tmp/a-bold.ttf",
            file_hash="sha256:def:index=0",
            platform="linux",
            fallback_used=False,
            bold=True,
        ),
    )
    assert compute_font_manifest_hash(fonts) == compute_font_manifest_hash(list(reversed(fonts)))


@pytest.mark.unit
def test_measurement_covers_cjk_latin_digits_punctuation() -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    service = TextMeasurementService()
    style = default_presentation_design_system().typography.body
    widths = {
        "cjk": service.measure_width_pt("汉", style=style),
        "latin": service.measure_width_pt("W", style=style),
        "digit": service.measure_width_pt("8", style=style),
        "punct": service.measure_width_pt("，", style=style),
    }
    assert all(value > 0 for value in widths.values())
    assert widths["punct"] < widths["cjk"]
    assert service.measurement_engine == MEASUREMENT_ENGINE_FREETYPE
    assert service.font_manifest_hash() == build_measurement_font_bundle().font_manifest_hash


@pytest.mark.unit
def test_bold_and_regular_measured_separately() -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    regular = build_font_manifest(DEFAULT_LATIN_FONT, bold=False)
    bold = build_font_manifest(DEFAULT_LATIN_FONT, bold=True)
    assert regular.file_hash != bold.file_hash
    assert regular.bold is False
    assert bold.bold is True

    style = default_presentation_design_system().typography.body.model_copy(
        update={"font_family": DEFAULT_LATIN_FONT, "font_family_latin": DEFAULT_LATIN_FONT}
    )
    service = TextMeasurementService()
    sample = "Archium WIDTH 2026"
    assert service.measure_width_pt(sample, style=style.model_copy(update={"font_weight": 700})) > (
        service.measure_width_pt(sample, style=style.model_copy(update={"font_weight": 400}))
    )


@pytest.mark.unit
def test_line_height_uses_max_of_design_and_glyph() -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    service = TextMeasurementService()
    body = default_presentation_design_system().typography.body
    tight = body.model_copy(update={"line_height": body.font_size * 0.5})
    loose = body.model_copy(update={"line_height": body.font_size * 3.0})
    tight_h = service._effective_line_height_in(tight)  # noqa: SLF001
    loose_h = service._effective_line_height_in(loose)  # noqa: SLF001
    assert loose_h == pytest.approx(loose.line_height / 72.0)
    assert tight_h >= tight.line_height / 72.0
    assert tight_h < loose_h


@pytest.mark.unit
def test_pptx_theme_families_align_with_measurement_defaults() -> None:
    design = default_presentation_design_system()
    theme = design_system_to_pptx_theme(design)
    assert theme["fonts"]["body"] == design.typography.body.font_family
    assert design.typography.body.font_family == DEFAULT_CJK_FONT
    assert (design.typography.body.font_family_latin or DEFAULT_LATIN_FONT) == DEFAULT_LATIN_FONT
