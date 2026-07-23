"""Page-type vocabulary authorities and explicit cross-maps (DOM-005).

These enums are **not** interchangeable. Convert only through this module.

| Enum | Authority |
|------|-----------|
| ``SlideType`` | ``SlideSpec`` rhetorical / content-planning type |
| ``FunctionalSlideType`` | Deck narrative function (induction / schema) |
| ``TemplatePageType`` | Template Studio layout page kind |
| ``SpecSlide.layout`` | Legacy PresentationSpec template id (string) |

``LayoutFamily`` is geometry selection (DOM-006) — not a page-type synonym.
"""

from __future__ import annotations

from archium.domain.enums import SlideType
from archium.domain.visual.architectural_template import TemplatePageType
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)

# ---------------------------------------------------------------------------
# FunctionalSlideType → SlideType (narrative function → planning type)
# ---------------------------------------------------------------------------

FUNCTIONAL_TO_SLIDE_TYPE: dict[FunctionalSlideType, SlideType] = {
    FunctionalSlideType.COVER: SlideType.TITLE,
    FunctionalSlideType.AGENDA: SlideType.SECTION,
    FunctionalSlideType.SECTION_DIVIDER: SlideType.SECTION,
    FunctionalSlideType.EXECUTIVE_SUMMARY: SlideType.SUMMARY,
    FunctionalSlideType.DECISION: SlideType.CONTENT,
    FunctionalSlideType.CONTENT: SlideType.CONTENT,
    FunctionalSlideType.CLOSING: SlideType.CLOSING,
    FunctionalSlideType.APPENDIX: SlideType.CONTENT,
    FunctionalSlideType.UNKNOWN: SlideType.CONTENT,
}

# Content refinements applied only when functional is CONTENT (or unknown).
_CONTENT_TO_SLIDE_TYPE: dict[ArchitecturalContentType, SlideType] = {
    ArchitecturalContentType.METRIC_SUMMARY: SlideType.DATA,
    ArchitecturalContentType.CASE_COMPARISON: SlideType.COMPARISON,
    ArchitecturalContentType.BEFORE_AFTER: SlideType.COMPARISON,
    ArchitecturalContentType.TIMELINE: SlideType.TIMELINE,
    ArchitecturalContentType.PHOTO_ANALYSIS: SlideType.IMAGE,
    ArchitecturalContentType.MULTI_IMAGE_GRID: SlideType.IMAGE,
    ArchitecturalContentType.COVER_VISUAL: SlideType.TITLE,
    ArchitecturalContentType.SECTION_VISUAL: SlideType.SECTION,
    ArchitecturalContentType.CONCLUSION: SlideType.CLOSING,
}


def slide_type_for_functional(
    functional: FunctionalSlideType,
    content: ArchitecturalContentType = ArchitecturalContentType.UNKNOWN,
) -> SlideType:
    """Map induction functional (+ optional content) onto SlideSpec.slide_type."""
    if functional in {
        FunctionalSlideType.CONTENT,
        FunctionalSlideType.UNKNOWN,
        FunctionalSlideType.APPENDIX,
        FunctionalSlideType.DECISION,
    }:
        refined = _CONTENT_TO_SLIDE_TYPE.get(content)
        if refined is not None:
            return refined
    return FUNCTIONAL_TO_SLIDE_TYPE[functional]


# ---------------------------------------------------------------------------
# FunctionalSlideType / ArchitecturalContentType → TemplatePageType
# ---------------------------------------------------------------------------

FUNCTIONAL_TO_TEMPLATE_PAGE: dict[FunctionalSlideType, TemplatePageType] = {
    FunctionalSlideType.COVER: TemplatePageType.COVER,
    FunctionalSlideType.AGENDA: TemplatePageType.AGENDA,
    FunctionalSlideType.SECTION_DIVIDER: TemplatePageType.SECTION,
    FunctionalSlideType.EXECUTIVE_SUMMARY: TemplatePageType.TEXT_ARGUMENT,
    FunctionalSlideType.DECISION: TemplatePageType.TEXT_ARGUMENT,
    FunctionalSlideType.CONTENT: TemplatePageType.UNKNOWN,
    FunctionalSlideType.CLOSING: TemplatePageType.CLOSING,
    FunctionalSlideType.APPENDIX: TemplatePageType.UNKNOWN,
    FunctionalSlideType.UNKNOWN: TemplatePageType.UNKNOWN,
}

CONTENT_TO_TEMPLATE_PAGE: dict[ArchitecturalContentType, TemplatePageType] = {
    ArchitecturalContentType.COVER_VISUAL: TemplatePageType.COVER,
    ArchitecturalContentType.SECTION_VISUAL: TemplatePageType.SECTION,
    ArchitecturalContentType.DRAWING_FOCUS: TemplatePageType.DRAWING_FOCUS,
    ArchitecturalContentType.PHOTO_ANALYSIS: TemplatePageType.PHOTO_GRID,
    ArchitecturalContentType.CASE_COMPARISON: TemplatePageType.CASE_COMPARISON,
    ArchitecturalContentType.BEFORE_AFTER: TemplatePageType.BEFORE_AFTER,
    ArchitecturalContentType.METRIC_SUMMARY: TemplatePageType.METRIC,
    ArchitecturalContentType.STRATEGY: TemplatePageType.TEXT_ARGUMENT,
    ArchitecturalContentType.PROCESS: TemplatePageType.PROCESS,
    ArchitecturalContentType.TIMELINE: TemplatePageType.TIMELINE,
    ArchitecturalContentType.DIAGRAM: TemplatePageType.DRAWING_FOCUS,
    ArchitecturalContentType.TEXT_ARGUMENT: TemplatePageType.TEXT_ARGUMENT,
    ArchitecturalContentType.IMAGE_TEXT_HYBRID: TemplatePageType.PHOTO_GRID,
    ArchitecturalContentType.MULTI_IMAGE_GRID: TemplatePageType.PHOTO_GRID,
    ArchitecturalContentType.CONCLUSION: TemplatePageType.CLOSING,
    ArchitecturalContentType.UNKNOWN: TemplatePageType.UNKNOWN,
}

# Candidate sets for affinity / co-planning (superset of primary map).
CONTENT_TO_TEMPLATE_PAGE_CANDIDATES: dict[ArchitecturalContentType, frozenset[TemplatePageType]] = {
    ArchitecturalContentType.COVER_VISUAL: frozenset({TemplatePageType.COVER}),
    ArchitecturalContentType.SECTION_VISUAL: frozenset({TemplatePageType.SECTION}),
    ArchitecturalContentType.DRAWING_FOCUS: frozenset({TemplatePageType.DRAWING_FOCUS}),
    ArchitecturalContentType.PHOTO_ANALYSIS: frozenset({TemplatePageType.PHOTO_GRID}),
    ArchitecturalContentType.CASE_COMPARISON: frozenset({TemplatePageType.CASE_COMPARISON}),
    ArchitecturalContentType.BEFORE_AFTER: frozenset({TemplatePageType.BEFORE_AFTER}),
    ArchitecturalContentType.METRIC_SUMMARY: frozenset({TemplatePageType.METRIC}),
    ArchitecturalContentType.STRATEGY: frozenset({TemplatePageType.TEXT_ARGUMENT}),
    ArchitecturalContentType.PROCESS: frozenset({TemplatePageType.PROCESS}),
    ArchitecturalContentType.TIMELINE: frozenset({TemplatePageType.TIMELINE}),
    ArchitecturalContentType.DIAGRAM: frozenset(
        {TemplatePageType.DRAWING_FOCUS, TemplatePageType.PROCESS}
    ),
    ArchitecturalContentType.TEXT_ARGUMENT: frozenset(
        {TemplatePageType.TEXT_ARGUMENT, TemplatePageType.AGENDA}
    ),
    ArchitecturalContentType.IMAGE_TEXT_HYBRID: frozenset(
        {TemplatePageType.PHOTO_GRID, TemplatePageType.TEXT_ARGUMENT}
    ),
    ArchitecturalContentType.MULTI_IMAGE_GRID: frozenset({TemplatePageType.PHOTO_GRID}),
    ArchitecturalContentType.CONCLUSION: frozenset(
        {TemplatePageType.CLOSING, TemplatePageType.TEXT_ARGUMENT}
    ),
    ArchitecturalContentType.UNKNOWN: frozenset({TemplatePageType.UNKNOWN}),
}


def template_page_for_functional(functional: FunctionalSlideType) -> TemplatePageType:
    return FUNCTIONAL_TO_TEMPLATE_PAGE[functional]


def template_page_for_content(content: ArchitecturalContentType) -> TemplatePageType:
    return CONTENT_TO_TEMPLATE_PAGE[content]


def template_page_candidates_for_content(
    content: ArchitecturalContentType,
) -> frozenset[TemplatePageType]:
    return CONTENT_TO_TEMPLATE_PAGE_CANDIDATES[content]


# Affinity candidates: SlideType → TemplatePageType (matcher / co-planning).
SLIDE_TYPE_TO_TEMPLATE_PAGE_CANDIDATES: dict[SlideType, frozenset[TemplatePageType]] = {
    SlideType.TITLE: frozenset({TemplatePageType.COVER, TemplatePageType.SECTION}),
    SlideType.SECTION: frozenset({TemplatePageType.SECTION}),
    SlideType.CONTENT: frozenset(
        {
            TemplatePageType.TEXT_ARGUMENT,
            TemplatePageType.PHOTO_GRID,
            TemplatePageType.DRAWING_FOCUS,
            TemplatePageType.METRIC,
        }
    ),
    SlideType.IMAGE: frozenset({TemplatePageType.PHOTO_GRID}),
    SlideType.COMPARISON: frozenset(
        {TemplatePageType.CASE_COMPARISON, TemplatePageType.BEFORE_AFTER}
    ),
    SlideType.TIMELINE: frozenset({TemplatePageType.TIMELINE, TemplatePageType.PROCESS}),
    SlideType.DATA: frozenset({TemplatePageType.METRIC}),
    SlideType.SUMMARY: frozenset({TemplatePageType.CLOSING, TemplatePageType.TEXT_ARGUMENT}),
    SlideType.CLOSING: frozenset({TemplatePageType.CLOSING}),
}


def template_page_candidates_for_slide_type(
    slide_type: SlideType,
) -> frozenset[TemplatePageType]:
    return SLIDE_TYPE_TO_TEMPLATE_PAGE_CANDIDATES[slide_type]


# ---------------------------------------------------------------------------
# SlideType → legacy SpecSlide.layout template ids
# ---------------------------------------------------------------------------

SPEC_LAYOUT_TITLE = "title"
SPEC_LAYOUT_SECTION = "section"
SPEC_LAYOUT_CONTENT_MESSAGE = "content_message"
SPEC_LAYOUT_CONTENT_BULLETS = "content_bullets"
SPEC_LAYOUT_IMAGE_CONTENT = "image_content"
SPEC_LAYOUT_IMAGE_FULL = "image_full"
SPEC_LAYOUT_COMPARISON = "comparison"
SPEC_LAYOUT_TIMELINE = "timeline"
SPEC_LAYOUT_DATA = "data"
SPEC_LAYOUT_CLOSING = "closing"
SPEC_LAYOUT_SITE_PLAN = "site_plan"
SPEC_LAYOUT_CHART = "chart"
SPEC_LAYOUT_TABLE = "table"

SLIDE_TYPE_TO_SPEC_LAYOUT: dict[SlideType, str] = {
    SlideType.TITLE: SPEC_LAYOUT_TITLE,
    SlideType.SECTION: SPEC_LAYOUT_SECTION,
    SlideType.CONTENT: SPEC_LAYOUT_CONTENT_MESSAGE,
    SlideType.IMAGE: SPEC_LAYOUT_IMAGE_FULL,
    SlideType.COMPARISON: SPEC_LAYOUT_COMPARISON,
    SlideType.TIMELINE: SPEC_LAYOUT_TIMELINE,
    SlideType.DATA: SPEC_LAYOUT_DATA,
    SlideType.SUMMARY: SPEC_LAYOUT_CLOSING,
    SlideType.CLOSING: SPEC_LAYOUT_CLOSING,
}


def spec_layout_for_slide_type(slide_type: SlideType) -> str:
    """Primary legacy Spec template id for a SlideType (DOM-003 derived path)."""
    return SLIDE_TYPE_TO_SPEC_LAYOUT[slide_type]
