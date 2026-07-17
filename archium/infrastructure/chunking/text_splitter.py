"""Recursive text splitting utilities."""

from __future__ import annotations

from archium.infrastructure.document_parsers._utils import normalize_whitespace

_BREAK_SEPARATORS = (
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    ".",
    "!",
    "?",
    "；",
    ";",
    "，",
    ",",
    " ",
)


def split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text on semantic boundaries with optional overlap."""
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    text_len = len(normalized)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            break_at = _find_break_point(normalized, start, end)
            if break_at <= start:
                break_at = end
        else:
            break_at = end

        piece = normalized[start:break_at].strip()
        if piece:
            chunks.append(piece)
        if break_at >= text_len:
            break
        start = max(break_at - chunk_overlap, start + 1)

    return chunks


def _find_break_point(text: str, start: int, end: int) -> int:
    window = text[start:end]
    min_pos = max(int(len(window) * 0.5), 1)

    for separator in _BREAK_SEPARATORS:
        index = window.rfind(separator)
        if index >= min_pos:
            return start + index + len(separator)
    return end
