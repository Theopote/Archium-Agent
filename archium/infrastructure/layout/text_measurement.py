"""Approximate text measurement for overflow detection (no real font metrics yet)."""

from __future__ import annotations

import re

from archium.domain.visual.design_system import TextStyleToken

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_WORD_RE = re.compile(r"[A-Za-z0-9]+|[^\s]", re.UNICODE)


class TextMeasurementService:
    """Estimate whether text fits a box given a typography token.

    Uses character-class heuristics suitable for Chinese/English mixed copy.
    Replace with real font measurement in a later edition.
    """

    def __init__(self, *, cjk_width_factor: float = 1.0, latin_width_factor: float = 0.55) -> None:
        self._cjk = cjk_width_factor
        self._latin = latin_width_factor

    def char_width_em(self, char: str) -> float:
        if char.isspace():
            return 0.35
        if _CJK_RE.match(char):
            return self._cjk
        if char.isdigit():
            return 0.6
        return self._latin

    def measure_width_pt(self, text: str, font_size_pt: float) -> float:
        return sum(self.char_width_em(ch) for ch in text) * font_size_pt

    def estimate_lines(
        self,
        text: str,
        *,
        box_width_in: float,
        style: TextStyleToken,
        dpi: float = 96.0,
    ) -> int:
        """Estimate wrapped line count for ``text`` inside a box width in inches."""
        if not text.strip():
            return 0
        box_width_pt = box_width_in * 72.0
        if box_width_pt <= 0:
            return 999

        # Honor explicit newlines first.
        paragraphs = text.replace("\r\n", "\n").split("\n")
        total_lines = 0
        for paragraph in paragraphs:
            if not paragraph:
                total_lines += 1
                continue
            line_width = 0.0
            lines = 1
            for token in _WORD_RE.findall(paragraph):
                token_w = self.measure_width_pt(token, style.font_size)
                # Soft wrap opportunity after latin words / always after CJK.
                if line_width > 0 and line_width + token_w > box_width_pt:
                    lines += 1
                    line_width = token_w
                else:
                    line_width += token_w
            total_lines += lines
        return total_lines

    def fits(
        self,
        text: str,
        *,
        box_width_in: float,
        box_height_in: float,
        style: TextStyleToken,
    ) -> bool:
        lines = self.estimate_lines(text, box_width_in=box_width_in, style=style)
        if style.max_lines is not None and lines > style.max_lines:
            return False
        line_height_in = style.line_height / 72.0
        needed = lines * line_height_in
        return needed <= box_height_in + 1e-6

    def overflow_amount(
        self,
        text: str,
        *,
        box_width_in: float,
        box_height_in: float,
        style: TextStyleToken,
    ) -> float:
        """Return inches of vertical overflow (0 if fits)."""
        lines = self.estimate_lines(text, box_width_in=box_width_in, style=style)
        line_height_in = style.line_height / 72.0
        needed = lines * line_height_in
        return max(0.0, needed - box_height_in)
