"""Product-flow stage: 大纲 — tree | intent cards | task meta."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.review_service import PresentationReviewService
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Storyline
from archium.domain.slide_intent import SlideIntent, slide_intents_from_page_instructions
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.pages import project_mission
from archium.ui.pages.flow import (
    render_flow_project_context,
    render_stage_header,
    render_stage_nav,
)
from archium.ui.planning_service import PlanningSnapshot, TASK_EXAMPLE_PROMPTS
from archium.ui.workspace_service import list_project_presentations


def _render_task_composer(project_id: UUID) -> None:
    st.markdown("#### 汇报任务")
    st.caption("用一两段话说明对象、目的与必须出现的内容。")
    if "outline_task_draft" not in st.session_state:
        st.session_state.outline_task_draft = st.session_state.get("mission_task_draft", "")
    example = st.selectbox(
        "示例（可选）",
        options=["（不使用示例）", *TASK_EXAMPLE_PROMPTS],
        key="outline_task_example",
    )
    if example != "（不使用示例）" and not st.session_state.outline_task_draft:
        st.session_state.outline_task_draft = example
    task = st.text_area(
        "任务描述",
        height=140,
        placeholder="例如：面向院领导汇报清凉寺前期策划，约 15 页，需覆盖现状问题、概念方案与下一步决策…",
        key="outline_task_draft",
    )
    if st.button("生成大纲", type="primary", use_container_width=True, key="outline_generate"):
        st.session_state.mission_task_draft = task
        project_mission.start_outline_planning(project_id, task)


def _load_outline_storyline(
    project_id: UUID,
) -> tuple[OutlinePlan | None, Storyline | None, list]:
    with get_session() as session:
        presentations = list_project_presentations(session, project_id)
        if not presentations:
            return None, None, []
        latest = presentations[0]
        context = PresentationReviewService(session).get_review_context(latest.id)
        if context is None:
            return None, None, []
        return context.outline, context.storyline, list(context.slides or [])


def _intent_cards_from_sources(
    *,
    outline: OutlinePlan | None,
    snapshot: PlanningSnapshot,
    slides: list,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []

    if outline is not None and outline.page_intents:
        for intent in outline.page_intents:
            cards.append(_card_from_slide_intent(intent, title_fallback=f"第 {intent.order + 1} 页"))
        return cards

    if outline is not None and outline.sections:
        order = 0
        for section in sorted(outline.sections, key=lambda item: item.order):
            if not section.expanded:
                continue
            for _ in range(max(1, section.estimated_slide_count)):
                cards.append(
                    {
                        "title": section.title,
                        "conclusion": section.key_message,
                        "task": section.purpose,
                        "evidence": "、".join(section.evidence_requirements[:4]) or "—",
                        "assets": "、".join(section.required_assets[:4]) or "—",
                        "page_type": section.category or "general",
                        "status": "已规划",
                    }
                )
                order += 1
        if cards:
            return cards

    request = snapshot.presentation_request
    if request is not None and request.page_instructions:
        intents = slide_intents_from_page_instructions(list(request.page_instructions))
        for intent in intents:
            cards.append(_card_from_slide_intent(intent, title_fallback=f"第 {intent.order + 1} 页"))
        if cards:
            return cards

    for index, slide in enumerate(slides):
        title = getattr(slide, "title", None) or f"第 {index + 1} 页"
        message = getattr(slide, "message", None) or getattr(slide, "core_message", None) or ""
        intent = getattr(slide, "intent", None) or ""
        cards.append(
            {
                "title": str(title),
                "conclusion": str(message) or "—",
                "task": str(intent) or "—",
                "evidence": "—",
                "assets": "—",
                "page_type": str(getattr(slide, "slide_type", None) or "—"),
                "status": "已有页面",
            }
        )
    return cards


def _card_from_slide_intent(intent: SlideIntent, *, title_fallback: str) -> dict[str, str]:
    title = intent.notes.strip() or intent.page_task.strip() or title_fallback
    if len(title) > 40:
        title = title[:40] + "…"
    return {
        "title": title,
        "conclusion": intent.central_conclusion.strip() or "—",
        "task": intent.page_task.strip() or "—",
        "evidence": "、".join(intent.required_evidence[:4]) or "—",
        "assets": "、".join(intent.required_assets[:4]) or "—",
        "page_type": intent.expected_layout.strip() or "—",
        "status": "意图已设",
    }


def _render_chapter_tree(
    *,
    outline: OutlinePlan | None,
    storyline: Storyline | None,
    cards: list[dict[str, str]],
) -> None:
    st.markdown("**章节与页面树**")
    if outline is not None and outline.sections:
        page_index = 0
        for section in sorted(outline.sections, key=lambda item: item.order):
            mark = "▾" if section.expanded else "▸"
            st.markdown(f"{mark} **{section.title}** · {section.estimated_slide_count} 页")
            count = max(1, section.estimated_slide_count) if section.expanded else 0
            for _ in range(count):
                if page_index < len(cards):
                    title = cards[page_index]["title"]
                    if st.button(
                        f"　{page_index + 1:02d}  {title}",
                        key=f"outline_tree_page_{page_index}",
                        use_container_width=True,
                    ):
                        st.session_state.outline_selected_card = page_index
                        st.rerun()
                page_index += 1
        return
    if storyline is not None and storyline.chapters:
        for chapter in sorted(storyline.chapters, key=lambda item: item.order):
            st.markdown(f"▸ **{chapter.title}**")
            if chapter.purpose:
                st.caption(chapter.purpose)
        if cards:
            for index, card in enumerate(cards):
                if st.button(
                    f"{index + 1:02d}  {card['title']}",
                    key=f"outline_tree_page_{index}",
                    use_container_width=True,
                ):
                    st.session_state.outline_selected_card = index
                    st.rerun()
        return
    if cards:
        for index, card in enumerate(cards):
            if st.button(
                f"{index + 1:02d}  {card['title']}",
                key=f"outline_tree_page_{index}",
                use_container_width=True,
            ):
                st.session_state.outline_selected_card = index
                st.rerun()
        return
    st.caption("生成大纲后将显示章节与页面树。")


def _render_intent_cards(cards: list[dict[str, str]]) -> None:
    st.markdown("**页面意图卡**")
    if not cards:
        st.info("尚无页面意图。先描述汇报任务并生成大纲。")
        return
    selected = int(st.session_state.get("outline_selected_card", 0) or 0)
    selected = max(0, min(selected, len(cards) - 1))
    st.session_state.outline_selected_card = selected
    labels = [f"{index:02d} {card['title']}" for index, card in enumerate(cards, start=1)]
    choice = st.selectbox(
        "选择页面",
        options=list(range(len(cards))),
        index=selected,
        format_func=lambda value: labels[value],
        key="outline_card_select",
    )
    st.session_state.outline_selected_card = int(choice)
    card = cards[int(choice)]
    with st.container(border=True):
        st.markdown(f"**页面标题**  \n{card['title']}")
        st.markdown(f"**中心结论**  \n{card['conclusion']}")
        st.markdown(f"**页面任务**  \n{card['task']}")
        st.markdown(f"**证据**  \n{card['evidence']}")
        st.markdown(f"**指定素材**  \n{card['assets']}")
        meta = st.columns(2)
        meta[0].markdown(f"**页面类型**  \n{card['page_type']}")
        meta[1].markdown(f"**状态**  \n{card['status']}")


def _render_task_meta(
    *,
    snapshot: PlanningSnapshot,
    outline: OutlinePlan | None,
    storyline: Storyline | None,
) -> None:
    request = snapshot.presentation_request
    mission = snapshot.mission

    if outline is not None:
        st.markdown(f"**汇报任务**  \n{outline.title}")
        st.caption(outline.purpose)
        st.markdown(f"**受众**  \n{outline.audience}")
        st.markdown(f"**页数**  \n{outline.target_slide_count}")
        arc = "—"
        if storyline is not None:
            arc = storyline.thesis or storyline.narrative_pattern
        st.markdown(f"**叙事弧线**  \n{arc}")
        return

    if request is not None:
        st.markdown(f"**汇报任务**  \n{request.title}")
        st.caption(request.purpose or request.core_message or "—")
        st.markdown(f"**受众**  \n{request.audience or '—'}")
        st.markdown(f"**页数**  \n{request.target_slide_count}")
        st.markdown(
            f"**叙事弧线**  \n{request.core_message or '、'.join(request.required_sections[:4]) or '—'}"
        )
        return

    if mission is not None:
        st.markdown(f"**汇报任务**  \n{mission.title}")
        st.caption(mission.task_statement)
        audience = "、".join(s.name for s in mission.stakeholders[:4] if s.name) or "—"
        st.markdown(f"**受众**  \n{audience}")
        st.markdown("**页数**  \n待确认")
        st.markdown("**叙事弧线**  \n待确认")
        return

    st.caption("尚未确认汇报任务。")

def _render_default_outline(project_id: UUID, snapshot: PlanningSnapshot) -> None:
    has_mission = snapshot.mission is not None
    has_request = snapshot.presentation_request is not None
    outline, storyline, slides = _load_outline_storyline(project_id)
    cards = _intent_cards_from_sources(outline=outline, snapshot=snapshot, slides=slides)

    if not has_mission and not has_request and outline is None and not cards:
        st.info("尚未确认大纲。先描述汇报任务，再生成结构。")
        _render_task_composer(project_id)
        return

    left, mid, right = st.columns([1.05, 1.6, 1.1], gap="medium")
    with left:
        _render_chapter_tree(outline=outline, storyline=storyline, cards=cards)
    with mid:
        _render_intent_cards(cards)
    with right:
        _render_task_meta(snapshot=snapshot, outline=outline, storyline=storyline)

    st.divider()
    cols = st.columns(3)
    with cols[0]:
        if st.button("重新规划", use_container_width=True, key="outline_replan"):
            project_mission.reset_planning_session()
            st.rerun()
    with cols[1]:
        ready = has_request or has_mission or outline is not None or bool(cards)
        if st.button(
            "确认大纲并进入生成",
            type="primary",
            use_container_width=True,
            disabled=not ready,
            key="outline_confirm",
        ):
            st.switch_page(get_app_page("generate"))
    with cols[2]:
        from archium.ui import icons

        st.page_link(get_app_page("generate"), label="直接前往生成", icon=icons.GENERATE)

    if not has_request and has_mission:
        with st.expander("继续完善任务描述", expanded=False):
            _render_task_composer(project_id)


def render() -> None:
    render_stage_header("outline")
    st.caption("确认章节、页面意图与汇报任务。高级六步规划可按需打开。")

    project_id = render_flow_project_context(allow_create=False, key_prefix="outline")
    if project_id is None:
        render_stage_nav("outline")
        return

    snapshot = project_mission.load_planning_snapshot(project_id)
    _render_default_outline(project_id, snapshot)

    st.divider()
    show_advanced = st.toggle(
        "高级任务规划",
        value=False,
        key="outline_advanced_planning",
        help="打开后显示完整六步规划器。",
    )
    if show_advanced:
        project_mission.render(embedded=True)

    st.divider()
    render_stage_nav("outline")
