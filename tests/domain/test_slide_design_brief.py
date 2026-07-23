"""Tests for SlideDesignBrief domain models."""

from __future__ import annotations

from archium.domain.enums import ApprovalStatus
from archium.domain.slide_design_brief import (
    SlideDesignBrief,
    default_drawing_policy,
    infer_primary_visual_type,
)


def test_infer_primary_visual_type_for_drawing_page() -> None:
    assert infer_primary_visual_type("drawing_focus") == "drawing"
    assert infer_primary_visual_type("photo_evidence_grid") == "photo"


def test_approved_brief_mark_changes_pending() -> None:
    brief = SlideDesignBrief(
        page_order=0,
        page_task="解释交通组织",
        status=ApprovalStatus.APPROVED,
    )
    brief.mark_changes_pending()
    assert brief.status == ApprovalStatus.CHANGES_PENDING


def test_legacy_ready_for_review_coerces_to_pending() -> None:
    brief = SlideDesignBrief.model_validate(
        {
            "page_order": 0,
            "page_task": "解释交通组织",
            "status": "ready_for_review",
        }
    )
    assert brief.status == ApprovalStatus.PENDING
    brief.mark_ready_for_review()  # already pending; draft-only transition
    draft = SlideDesignBrief(page_order=1, page_task="任务", status=ApprovalStatus.DRAFT)
    draft.mark_ready_for_review()
    assert draft.status == ApprovalStatus.PENDING


def test_drawing_policy_defaults_protect_annotations() -> None:
    policy = default_drawing_policy()
    assert policy.fit_mode == "contain"
    assert policy.forbid_cover_crop is True
    assert policy.preserve_annotations is True
