"""DOM-005: page-type authorities and explicit cross-maps."""

from __future__ import annotations

from archium.domain.enums import SlideType
from archium.domain.visual.architectural_template import TemplatePageType
from archium.domain.visual.page_type_catalog import (
    CONTENT_TO_TEMPLATE_PAGE,
    CONTENT_TO_TEMPLATE_PAGE_CANDIDATES,
    FUNCTIONAL_TO_SLIDE_TYPE,
    FUNCTIONAL_TO_TEMPLATE_PAGE,
    SLIDE_TYPE_TO_SPEC_LAYOUT,
    SLIDE_TYPE_TO_TEMPLATE_PAGE_CANDIDATES,
    slide_type_for_functional,
    spec_layout_for_slide_type,
    template_page_candidates_for_content,
    template_page_for_content,
    template_page_for_functional,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)


def test_functional_to_slide_type_covers_all_members() -> None:
    assert set(FUNCTIONAL_TO_SLIDE_TYPE) == set(FunctionalSlideType)


def test_functional_to_template_page_covers_all_members() -> None:
    assert set(FUNCTIONAL_TO_TEMPLATE_PAGE) == set(FunctionalSlideType)


def test_content_to_template_page_covers_all_members() -> None:
    assert set(CONTENT_TO_TEMPLATE_PAGE) == set(ArchitecturalContentType)
    assert set(CONTENT_TO_TEMPLATE_PAGE_CANDIDATES) == set(ArchitecturalContentType)


def test_slide_type_maps_cover_all_members() -> None:
    assert set(SLIDE_TYPE_TO_SPEC_LAYOUT) == set(SlideType)
    assert set(SLIDE_TYPE_TO_TEMPLATE_PAGE_CANDIDATES) == set(SlideType)


def test_slide_type_for_functional_cover_and_content_refinement() -> None:
    assert slide_type_for_functional(FunctionalSlideType.COVER) == SlideType.TITLE
    assert slide_type_for_functional(FunctionalSlideType.AGENDA) == SlideType.SECTION
    assert (
        slide_type_for_functional(
            FunctionalSlideType.CONTENT,
            ArchitecturalContentType.METRIC_SUMMARY,
        )
        == SlideType.DATA
    )
    assert (
        slide_type_for_functional(
            FunctionalSlideType.AGENDA,
            ArchitecturalContentType.METRIC_SUMMARY,
        )
        == SlideType.SECTION
    )


def test_template_page_helpers_match_maps() -> None:
    assert template_page_for_functional(FunctionalSlideType.COVER) == TemplatePageType.COVER
    assert (
        template_page_for_content(ArchitecturalContentType.DRAWING_FOCUS)
        == TemplatePageType.DRAWING_FOCUS
    )
    candidates = template_page_candidates_for_content(ArchitecturalContentType.DIAGRAM)
    assert TemplatePageType.DRAWING_FOCUS in candidates
    assert TemplatePageType.PROCESS in candidates


def test_spec_layout_for_slide_type() -> None:
    assert spec_layout_for_slide_type(SlideType.TITLE) == "title"
    assert spec_layout_for_slide_type(SlideType.CONTENT) == "content_message"
