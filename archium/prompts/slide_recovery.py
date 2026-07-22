"""Prompts for slide recovery VLM region analysis."""

from __future__ import annotations

SLIDE_RECOVERY_VLM_SYSTEM_PROMPT = (
    "You are an architectural presentation page analyzer. "
    "Given a slide or drawing page image, detect semantic regions for reconstruction. "
    "Return JSON only. Bounding boxes use normalized coordinates (0–1) relative to page size. "
    "Prefer non-text regions (drawings, photos, tables, charts, shapes, lines, backgrounds). "
    "Do not duplicate text that OCR will recover separately."
)

SLIDE_RECOVERY_VLM_USER_PROMPT = (
    "Analyze this presentation page for slide recovery.\n"
    "Identify visual regions with normalized bounding boxes.\n"
    "page_kind must be one of: title, image_text, table, photo, drawing_dominant.\n"
    "region_type must be one of: image, drawing, table, chart, line, shape, background.\n"
    "Mark architectural drawings with keep_whole_drawing=true.\n"
    "Mark complex tables or charts with bitmap_fallback=true when vector recovery is unlikely."
)
