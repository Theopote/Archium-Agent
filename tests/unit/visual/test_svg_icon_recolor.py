from __future__ import annotations

from pathlib import Path

from archium.application.visual.icon_stroke_resolve import (
    ICON_STROKE_TOKEN,
    resolve_icon_stroke_color,
)
from archium.application.visual.svg_icon_recolor import (
    PACK_DEFAULT_STROKE,
    is_architectural_icon_ref,
    materialize_recolored_icon,
    recolor_icon_svg_text,
)
from archium.domain.visual.defaults import default_presentation_design_system


def test_is_architectural_icon_ref() -> None:
    assert is_architectural_icon_ref("icon:pedestrian_flow")
    assert not is_architectural_icon_ref("uuid-here")
    assert not is_architectural_icon_ref(None)


def test_recolor_icon_svg_text_remaps_pack_stroke() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="#1a1a1a" stroke-width="1.75">'
        '<path d="M12 8v5"/></svg>'
    )
    recolored = recolor_icon_svg_text(svg, "#E63946")
    assert 'stroke="#E63946"' in recolored
    assert PACK_DEFAULT_STROKE.lower() not in recolored.lower()


def test_materialize_recolored_icon_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "icon.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="#1a1a1a"><path d="M12 8v5"/></svg>',
        encoding="utf-8",
    )
    cache = tmp_path / "cache"
    first = materialize_recolored_icon(source, "#112233", cache_dir=cache)
    second = materialize_recolored_icon(source, "#112233", cache_dir=cache)
    assert first == second
    assert first.is_file()
    assert 'stroke="#112233"' in first.read_text(encoding="utf-8")


def test_resolve_icon_stroke_color_uses_accent_token() -> None:
    design = default_presentation_design_system().model_copy(deep=True)
    design.colors.accent = "#C45C26"
    assert resolve_icon_stroke_color(design) == "#C45C26"
    assert ICON_STROKE_TOKEN == "accent"
