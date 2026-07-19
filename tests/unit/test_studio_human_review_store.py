"""Unit tests for human review JSON persistence."""

from __future__ import annotations

from uuid import uuid4

from archium.application.studio_human_review_store import (
    load_slide_review,
    save_slide_review,
)
from archium.config.settings import Settings
from archium.domain.visual.benchmark import HumanVisualReview


def test_save_and_load_slide_review(tmp_path) -> None:  # noqa: ANN001
    presentation_id = uuid4()
    slide_id = uuid4()
    settings = Settings(output_path=tmp_path)
    review = HumanVisualReview(
        case_id=str(slide_id),
        information_hierarchy=4,
        visual_focus=4,
        reading_order=4,
        image_text_relationship=4,
        whitespace_density=4,
        architectural_expression=4,
        aesthetic_finish=4,
        editability=4,
        accepted=True,
        reviewer_notes="studio test",
    )
    path = save_slide_review(presentation_id, slide_id, review, settings=settings)
    assert path.is_file()
    loaded = load_slide_review(presentation_id, slide_id, settings=settings)
    assert loaded is not None
    assert loaded.reviewer_notes == "studio test"
    assert loaded.accepted is True
