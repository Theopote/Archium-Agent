"""Text measurement for layout overflow detection using real font metrics when available."""

from __future__ import annotations

import re

from archium.domain.visual.design_system import TextStyleToken
from archium.infrastructure.layout.font_manifest import (
    MEASUREMENT_ENGINE_FREETYPE,
    MEASUREMENT_ENGINE_HEURISTIC,
    FontManifestBundle,
    build_measurement_font_bundle,
)
from archium.infrastructure.layout.font_resolver import (
    TruetypeFont,
    fonts_available,
    load_truetype_font,
)
from archium.logging import get_logger

logger = get_logger(__name__, operation="text_measurement")

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+|[^\s]", re.UNICODE)
_BOLD_WEIGHT_THRESHOLD = 600


class TextMeasurementService:
    """Estimate whether text fits a box given a typography token.

    Real path: Pillow FreeType (``ImageFont.truetype`` → ``getbbox``) with the same
    logical families PPTX uses (Microsoft YaHei + Arial), resolved via
    ``FontManifest`` / platform fallbacks (Noto/Liberation on Linux CI).

    Heuristic path: character-class width factors only when fonts or Pillow are
    unavailable.
    """

    def __init__(
        self,
        *,
        cjk_width_factor: float = 1.0,
        latin_width_factor: float = 0.55,
        dpi: float = 96.0,
        use_heuristic_fallback: bool = True,
    ) -> None:
        self._cjk = cjk_width_factor
        self._latin = latin_width_factor
        self._dpi = dpi
        self._use_heuristic_fallback = use_heuristic_fallback
        self._heuristic_warned = False

    @property
    def uses_real_metrics(self) -> bool:
        return fonts_available()

    @property
    def measurement_engine(self) -> str:
        if self._can_use_real_metrics():
            return MEASUREMENT_ENGINE_FREETYPE
        return MEASUREMENT_ENGINE_HEURISTIC

    def font_manifest_bundle(self) -> FontManifestBundle:
        """Provenance for fonts this service measures against (bind to visual baselines)."""
        return build_measurement_font_bundle()

    def font_manifest_hash(self) -> str:
        return self.font_manifest_bundle().font_manifest_hash

    def char_width_em(self, char: str) -> float:
        if char.isspace():
            return 0.35
        if _CJK_RE.match(char):
            return self._cjk
        if char.isdigit():
            return 0.6
        return self._latin

    def measure_width_pt(
        self,
        text: str,
        font_size_pt: float | None = None,
        *,
        style: TextStyleToken | None = None,
    ) -> float:
        if style is None:
            if font_size_pt is None:
                msg = "measure_width_pt requires font_size_pt or style"
                raise ValueError(msg)
            style = TextStyleToken(
                font_family="Microsoft YaHei",
                font_family_latin="Arial",
                font_size=font_size_pt,
                font_weight=400,
                line_height=font_size_pt * 1.2,
                color_token="text.primary",
            )
        effective_style = (
            style
            if font_size_pt is None
            else style.model_copy(update={"font_size": font_size_pt})
        )
        if self._can_use_real_metrics():
            return self._measure_width_pt_real(text, effective_style)
        return sum(self.char_width_em(ch) for ch in text) * effective_style.font_size

    def estimate_lines(
        self,
        text: str,
        *,
        box_width_in: float,
        style: TextStyleToken,
        dpi: float = 96.0,
        language: str | None = None,
    ) -> int:
        """Estimate wrapped line count for ``text`` inside a box width in inches.

        Callers (especially capacity) must pass a full ``TextStyleToken`` so
        family / size / weight / line_height are applied. ``language`` is an
        explicit hint (``zh`` / ``en`` / ``mixed``) for font selection bias.
        """
        if not text.strip():
            return 0
        box_width_pt = box_width_in * 72.0
        if box_width_pt <= 0:
            return 999
        effective = _style_with_language(style, language)

        if self._can_use_real_metrics():
            return self._estimate_lines_real(
                text, box_width_pt=box_width_pt, style=effective, dpi=dpi
            )

        return self._estimate_lines_heuristic(
            text, box_width_pt=box_width_pt, style=effective
        )

    def estimate_block_height_in(
        self,
        text: str,
        *,
        box_width_in: float,
        style: TextStyleToken,
        vertical_slack_in: float = 0.0,
        dpi: float | None = None,
        language: str | None = None,
    ) -> float:
        """Estimated vertical space for wrapped text (inches), optional repair slack.

        Requires styled metrics: font family, size, weight, and line height come
        from ``style``; wrap width from ``box_width_in``; script bias from ``language``.
        """
        resolved_dpi = dpi if dpi is not None else self._dpi
        effective = _style_with_language(style, language)
        lines = self.estimate_lines(
            text,
            box_width_in=box_width_in,
            style=effective,
            dpi=resolved_dpi,
            language=language,
        )
        if lines == 0:
            return vertical_slack_in
        line_height_in = self._effective_line_height_in(effective, dpi=resolved_dpi)
        block = lines * line_height_in
        if self._can_use_real_metrics():
            block += self._descender_slack_in(effective, dpi=resolved_dpi)
        return block + vertical_slack_in

    def fits(
        self,
        text: str,
        *,
        box_width_in: float,
        box_height_in: float,
        style: TextStyleToken,
        vertical_tolerance_in: float = 0.0,
        language: str | None = None,
    ) -> bool:
        needed = self.estimate_block_height_in(
            text,
            box_width_in=box_width_in,
            style=style,
            language=language,
        )
        if style.max_lines is not None:
            lines = self.estimate_lines(
                text, box_width_in=box_width_in, style=style, language=language
            )
            if lines > style.max_lines:
                return False
        return needed <= box_height_in + vertical_tolerance_in + 1e-6

    def overflow_amount(
        self,
        text: str,
        *,
        box_width_in: float,
        box_height_in: float,
        style: TextStyleToken,
        vertical_tolerance_in: float = 0.0,
        language: str | None = None,
    ) -> float:
        """Return inches of vertical overflow after tolerance (0 if fits)."""
        needed = self.estimate_block_height_in(
            text,
            box_width_in=box_width_in,
            style=style,
            language=language,
        )
        if style.max_lines is not None:
            lines = self.estimate_lines(
                text, box_width_in=box_width_in, style=style, language=language
            )
            if lines > style.max_lines:
                line_height_in = self._effective_line_height_in(style)
                needed = max(needed, style.max_lines * line_height_in)
        return max(0.0, needed - box_height_in - vertical_tolerance_in)

    def _can_use_real_metrics(self) -> bool:
        if fonts_available():
            return True
        if self._use_heuristic_fallback and not self._heuristic_warned:
            logger.info(
                "Text measurement falling back to character-width heuristics "
                "(install Pillow + Noto/Liberation or Windows fonts for real metrics)"
            )
            self._heuristic_warned = True
        return False

    def _font_size_px(self, font_size_pt: float, dpi: float) -> int:
        return max(1, round(font_size_pt * dpi / 72.0))

    def _font_for_char(self, char: str, style: TextStyleToken, size_px: int) -> TruetypeFont | None:
        bold = style.font_weight >= _BOLD_WEIGHT_THRESHOLD
        # Per-glyph script detection; language hint may already have biased families.
        if _CJK_RE.match(char):
            family = style.font_family
        else:
            family = style.font_family_latin or style.font_family
        return load_truetype_font(family, bold=bold, size_px=size_px)

    def _measure_glyph_width_pt(self, char: str, style: TextStyleToken, *, dpi: float) -> float:
        size_px = self._font_size_px(style.font_size, dpi)
        font = self._font_for_char(char, style, size_px)
        if font is None:
            return self.char_width_em(char) * style.font_size
        bbox = font.getbbox(char)
        width_px = float(max(0, bbox[2] - bbox[0]))
        width_px += self._letter_spacing_px(style, dpi)
        return width_px * 72.0 / dpi

    def _measure_string_width_pt(self, text: str, style: TextStyleToken, *, dpi: float) -> float:
        if not text:
            return 0.0
        return sum(self._measure_glyph_width_pt(char, style, dpi=dpi) for char in text)

    def _measure_width_pt_real(self, text: str, style: TextStyleToken) -> float:
        return self._measure_string_width_pt(text, style, dpi=self._dpi)

    def _letter_spacing_px(self, style: TextStyleToken, dpi: float) -> float:
        if abs(style.letter_spacing) <= 1e-9:
            return 0.0
        # Design tokens store letter spacing in points.
        return style.letter_spacing * dpi / 72.0

    def _estimate_lines_heuristic(
        self,
        text: str,
        *,
        box_width_pt: float,
        style: TextStyleToken,
    ) -> int:
        paragraphs = text.replace("\r\n", "\n").split("\n")
        total_lines = 0
        for paragraph in paragraphs:
            if not paragraph:
                total_lines += 1
                continue
            line_width = 0.0
            lines = 1
            for token in _LATIN_WORD_RE.findall(paragraph):
                token_w = self.measure_width_pt(token, style.font_size)
                if line_width > 0 and line_width + token_w > box_width_pt:
                    lines += 1
                    line_width = token_w
                else:
                    line_width += token_w
            total_lines += lines
        return total_lines

    def _estimate_lines_real(
        self,
        text: str,
        *,
        box_width_pt: float,
        style: TextStyleToken,
        dpi: float,
    ) -> int:
        paragraphs = text.replace("\r\n", "\n").split("\n")
        total_lines = 0
        for paragraph in paragraphs:
            if not paragraph:
                total_lines += 1
                continue
            lines = 1
            line_width = 0.0
            index = 0
            while index < len(paragraph):
                char = paragraph[index]
                if char.isspace():
                    glyph_w = self._measure_glyph_width_pt(char, style, dpi=dpi)
                    if line_width > 0 and line_width + glyph_w > box_width_pt + 1e-6:
                        lines += 1
                        line_width = 0.0
                    else:
                        line_width += glyph_w
                    index += 1
                    continue

                if _CJK_RE.match(char):
                    end = index + 1
                    while end < len(paragraph) and _CJK_RE.match(paragraph[end]):
                        end += 1
                    token = paragraph[index:end]
                    index = end
                else:
                    end = index
                    while end < len(paragraph) and not paragraph[end].isspace() and not _CJK_RE.match(
                        paragraph[end]
                    ):
                        end += 1
                    token = paragraph[index:end]
                    index = end

                token_w = self._measure_string_width_pt(token, style, dpi=dpi)
                if token_w > box_width_pt + 1e-6 and token and _CJK_RE.match(token[0]):
                    for glyph in token:
                        glyph_w = self._measure_glyph_width_pt(glyph, style, dpi=dpi)
                        if line_width > 0 and line_width + glyph_w > box_width_pt + 1e-6:
                            lines += 1
                            line_width = glyph_w
                        else:
                            line_width += glyph_w
                elif line_width > 0 and line_width + token_w > box_width_pt + 1e-6:
                    lines += 1
                    line_width = token_w
                else:
                    line_width += token_w
            total_lines += lines
        return total_lines

    def _effective_line_height_in(self, style: TextStyleToken, *, dpi: float | None = None) -> float:
        design_line_in = style.line_height / 72.0
        if not self._can_use_real_metrics():
            return design_line_in
        resolved_dpi = dpi if dpi is not None else self._dpi
        glyph_line_in = self._glyph_line_height_in(style, dpi=resolved_dpi)
        return max(design_line_in, glyph_line_in)

    def _glyph_line_height_in(self, style: TextStyleToken, *, dpi: float) -> float:
        """Natural single-line bbox height from mixed CJK/Latin sample glyphs."""
        sample = "Hg因，"
        size_px = self._font_size_px(style.font_size, dpi)
        max_height_px = 0.0
        for char in sample:
            font = self._font_for_char(char, style, size_px)
            if font is None:
                continue
            bbox = font.getbbox(char)
            max_height_px = max(max_height_px, float(bbox[3] - bbox[1]))
        if max_height_px <= 0:
            return style.line_height / 72.0
        return max_height_px / dpi

    def _descender_slack_in(self, style: TextStyleToken, *, dpi: float) -> float:
        """One-time bottom slack when glyph bbox exceeds design line height."""
        design_line_in = style.line_height / 72.0
        glyph_line_in = self._glyph_line_height_in(style, dpi=dpi)
        return max(0.0, glyph_line_in - design_line_in) * 0.5


def _style_with_language(style: TextStyleToken, language: str | None) -> TextStyleToken:
    """Apply language hint without inventing missing family/size/weight/line_height.

    Capacity callers must already supply a complete TextStyleToken; this only
    biases CJK vs Latin primary family when language is explicit.
    """
    if not language:
        return style
    normalized = language.strip().lower()
    if normalized.startswith("zh") or normalized in {"cjk", "mixed"}:
        if style.font_family_latin:
            return style
        return style.model_copy(update={"font_family_latin": "Arial"})
    if normalized.startswith("en") or normalized in {"latin", "western"}:
        latin = style.font_family_latin or style.font_family
        return style.model_copy(
            update={
                "font_family": latin,
                "font_family_latin": latin,
            }
        )
    return style
