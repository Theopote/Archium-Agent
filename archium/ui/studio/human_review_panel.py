"""Manual visual quality review for Presentation Studio slides."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.studio_human_review_store import (
    load_slide_review,
    save_slide_review,
)
from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_MAX_SCORE,
    HUMAN_REVIEW_MIN_SCORE,
    HUMAN_REVIEW_PASS_THRESHOLD,
    HumanVisualReview,
)
from archium.infrastructure.database.session import get_session
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.visual_service import SlideVisualSnapshot

REVIEW_DIMENSION_LABELS: dict[str, str] = {
    "information_hierarchy": "信息层级",
    "visual_focus": "视觉焦点",
    "reading_order": "阅读顺序",
    "image_text_relationship": "图文关系",
    "whitespace_density": "留白与密度",
    "architectural_expression": "建筑表达",
    "aesthetic_finish": "审美完成度",
    "editability": "可编辑性",
}


def _reviews_key(presentation_id: UUID) -> str:
    return f"studio_human_reviews_{presentation_id}"


def get_stored_human_review(
    *,
    presentation_id: UUID,
    slide_id: UUID,
) -> HumanVisualReview | None:
    cached = st.session_state.get(_reviews_key(presentation_id), {})
    if isinstance(cached, dict):
        payload = cached.get(str(slide_id))
        if isinstance(payload, dict):
            try:
                return HumanVisualReview.model_validate(payload)
            except Exception:
                pass
    with get_session() as session:
        return load_slide_review(
            session,
            presentation_id,
            slide_id,
            settings=get_ui_effective_settings(),
        )


def store_human_review(review: HumanVisualReview, *, presentation_id: UUID, slide_id: UUID) -> Path:
    settings = get_ui_effective_settings()
    with get_session() as session:
        path = save_slide_review(
            session,
            presentation_id,
            slide_id,
            review,
            settings=settings,
        )
    key = _reviews_key(presentation_id)
    store = dict(st.session_state.get(key) or {})
    store[str(slide_id)] = review.model_dump(mode="json")
    st.session_state[key] = store
    return path


def render_human_review_panel(
    *,
    presentation_id: UUID,
    slide_snapshot: SlideVisualSnapshot | None,
) -> None:
    """Render 9-dimension manual review for the current slide."""
    st.markdown("**人工视觉评审**")
    if slide_snapshot is None:
        st.caption("请选择页面后再评审。")
        return

    slide = slide_snapshot.slide
    case_id = str(slide.id)
    existing = get_stored_human_review(presentation_id=presentation_id, slide_id=slide.id)

    defaults = {
        field: getattr(existing, field, 4)
        for field in REVIEW_DIMENSION_LABELS
    }
    scores: dict[str, int] = {}
    for field, label in REVIEW_DIMENSION_LABELS.items():
        scores[field] = st.slider(
            label,
            min_value=HUMAN_REVIEW_MIN_SCORE,
            max_value=HUMAN_REVIEW_MAX_SCORE,
            value=int(defaults[field]),
            key=f"studio_human_review_{presentation_id}_{slide.id}_{field}",
        )

    major = st.text_area(
        "主要问题（每行一条）",
        value="\n".join(existing.major_problems if existing else []),
        height=72,
        key=f"studio_human_major_{slide.id}",
    )
    minor = st.text_area(
        "次要问题（每行一条）",
        value="\n".join(existing.minor_problems if existing else []),
        height=72,
        key=f"studio_human_minor_{slide.id}",
    )
    accepted = st.checkbox(
        "本页可接受交付",
        value=bool(existing.accepted if existing else False),
        key=f"studio_human_accept_{slide.id}",
    )
    notes = st.text_input(
        "评审备注",
        value=existing.reviewer_notes if existing else "",
        key=f"studio_human_notes_{slide.id}",
    )

    preview = HumanVisualReview(
        case_id=case_id,
        **scores,
        major_problems=[line.strip() for line in major.splitlines() if line.strip()],
        minor_problems=[line.strip() for line in minor.splitlines() if line.strip()],
        accepted=accepted,
        reviewer_notes=notes.strip(),
    )
    weighted = preview.weighted_score()
    st.caption(
        f"综合评分 {weighted:.2f} / 5 · "
        f"{'通过' if preview.passes_threshold() else '未达'} "
        f"交付阈值 {HUMAN_REVIEW_PASS_THRESHOLD}"
    )

    if st.button(
        "保存本页评审",
        use_container_width=True,
        key=f"studio_save_human_review_{slide.id}",
    ):
        path = store_human_review(preview, presentation_id=presentation_id, slide_id=slide.id)
        st.success(f"已保存人工评审（{path}）。")
        st.rerun()
