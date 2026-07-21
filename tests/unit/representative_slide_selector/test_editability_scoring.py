"""Unit tests for representative editability heuristic (V1.5)."""

from __future__ import annotations

from archium.application.visual.representative_slide_selector import compute_editability
from archium.domain.visual.reference_slide import (
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)


def _slide(*elements: ReferenceElement, **kwargs) -> ReferenceSlideSnapshot:
    return ReferenceSlideSnapshot(
        slide_index=kwargs.get("slide_index", 0),
        slide_id=kwargs.get("slide_id", "slide_001"),
        width=10.0,
        height=5.625,
        elements=list(elements),
        parse_warnings=kwargs.get("parse_warnings", []),
    )


def _text(**kwargs) -> ReferenceElement:
    defaults = dict(
        element_type=ReferenceElementType.TEXT,
        x=0.5,
        y=0.5,
        width=8.0,
        height=0.8,
        text="标题",
        semantic_role="title",
    )
    defaults.update(kwargs)
    return ReferenceElement(id=defaults.pop("id", "t1"), **defaults)


def test_clean_placeholder_page_scores_high() -> None:
    slide = _slide(
        ReferenceElement(
            id="ph1",
            element_type=ReferenceElementType.PLACEHOLDER,
            x=0.5,
            y=0.4,
            width=9.0,
            height=1.0,
            style_notes=["placeholder_hosts_text"],
        ),
        _text(id="body", y=1.5, semantic_role="body", text="论述正文"),
    )
    score, notes = compute_editability(slide)
    assert score >= 0.40
    assert "placeholders=1" in notes
    assert "top_text_slots=1" in notes


def test_full_page_background_penalized() -> None:
    clean = _slide(_text())
    dirty = _slide(
        ReferenceElement(
            id="bg",
            element_type=ReferenceElementType.IMAGE,
            x=0.0,
            y=0.0,
            width=10.0,
            height=5.625,
            style_notes=["hard_edit:full_page_background"],
        ),
        _text(y=4.5, height=0.5, text="caption"),
    )
    clean_score, _ = compute_editability(clean)
    dirty_score, notes = compute_editability(dirty)
    assert dirty_score < clean_score
    assert "full_page_background" in notes


def test_grouped_and_master_chrome_reduce_score() -> None:
    clean = _slide(_text(), _text(id="t2", y=1.5, text="body"))
    grouped = _slide(
        ReferenceElement(
            id="g1",
            element_type=ReferenceElementType.GROUP,
            x=0.5,
            y=0.5,
            width=8.0,
            height=3.0,
            style_notes=["hard_edit:group"],
            children=[
                _text(id="gc1", y=0.6, text="nested title"),
            ],
        )
    )
    master_chrome = _slide(
        _text(repeats_across_pages=True, likely_background_or_decoration=True),
        _text(id="footer", y=5.0, repeats_across_pages=True, text="页脚"),
        _text(id="body", y=1.5, text="正文"),
    )
    clean_score, _ = compute_editability(clean)
    grouped_score, g_notes = compute_editability(grouped)
    master_score, m_notes = compute_editability(master_chrome)
    assert grouped_score < clean_score
    assert "grouped_shapes=1" in g_notes
    assert master_score < clean_score
    assert "master_like_chrome=2" in m_notes


def test_hard_edit_tags_penalized_individually() -> None:
    base = _slide(_text())
    base_score, _ = compute_editability(base)

    smartart = _slide(
        _text(),
        ReferenceElement(
            id="sa",
            element_type=ReferenceElementType.SHAPE,
            x=2.0,
            y=2.0,
            width=4.0,
            height=2.0,
            style_notes=["hard_edit:smartart"],
        ),
    )
    locked = _slide(
        _text(),
        ReferenceElement(
            id="img",
            element_type=ReferenceElementType.IMAGE,
            x=5.0,
            y=1.0,
            width=3.0,
            height=2.0,
            style_notes=["hard_edit:locked", "hard_edit:picture_crop"],
        ),
    )
    sa_score, sa_notes = compute_editability(smartart)
    lock_score, lock_notes = compute_editability(locked)
    assert sa_score < base_score
    assert lock_score < base_score
    assert "hard_edit:smartart" in sa_notes
    assert "hard_edit:locked" in lock_notes
    assert "hard_edit:picture_crop" in lock_notes


def test_picture_placeholder_weaker_than_text_placeholder() -> None:
    text_ph = _slide(
        ReferenceElement(
            id="ph_t",
            element_type=ReferenceElementType.PLACEHOLDER,
            x=0.5,
            y=0.5,
            width=4.0,
            height=1.0,
            style_notes=["placeholder_hosts_text"],
        ),
    )
    pic_ph = _slide(
        ReferenceElement(
            id="ph_p",
            element_type=ReferenceElementType.PLACEHOLDER,
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.0,
            style_notes=["placeholder_hosts_picture"],
        ),
    )
    text_score, _ = compute_editability(text_ph)
    pic_score, _ = compute_editability(pic_ph)
    assert text_score > pic_score


def test_parse_warnings_reduce_editability() -> None:
    slide = _slide(_text(), parse_warnings=["missing font"])
    score, notes = compute_editability(slide)
    assert score < 0.5
    assert "slide_parse_warnings" in notes
