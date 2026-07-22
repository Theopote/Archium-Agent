"""Product-flow stage: 大纲 — tree | intent cards | task meta."""

from __future__ import annotations

from copy import deepcopy
from uuid import UUID

import streamlit as st

from archium.application.review_models import (
    OutlineSectionUpdate,
    OutlineUpdate,
    SlideAssetBindingUpdate,
    SlideIntentUpdate,
)
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
from archium.ui.planning_service import TASK_EXAMPLE_PROMPTS, PlanningSnapshot
from archium.ui.workspace_service import list_project_presentations

_PAGE_TYPE_OPTIONS = (
    "general",
    "title",
    "content",
    "photo_evidence_grid",
    "drawing_focus",
    "comparison",
    "summary",
    "data",
    "closing",
)


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


def _split_items(raw: str) -> list[str]:
    text = raw.replace("\n", "、").replace(",", "、").replace(";", "、")
    return [part.strip() for part in text.split("、") if part.strip()]


def _section_updates(outline: OutlinePlan) -> list[OutlineSectionUpdate]:
    return [
        OutlineSectionUpdate(
            id=section.id,
            title=section.title,
            purpose=section.purpose,
            key_message=section.key_message,
            order=section.order,
            estimated_slide_count=section.estimated_slide_count,
            evidence_requirements=list(section.evidence_requirements),
            required_assets=list(section.required_assets),
            required=section.required,
            expanded=section.expanded,
            category=section.category,
        )
        for section in sorted(outline.sections, key=lambda item: item.order)
    ]


def _intent_updates(intents: list[SlideIntent]) -> list[SlideIntentUpdate]:
    return [
        SlideIntentUpdate(
            order=intent.order,
            chapter_id=intent.chapter_id,
            page_task=intent.page_task,
            central_conclusion=intent.central_conclusion,
            required_evidence=list(intent.required_evidence),
            required_assets=list(intent.required_assets),
            forbidden_content=list(intent.forbidden_content),
            expected_layout=intent.expected_layout,
            notes=intent.notes,
        )
        for intent in sorted(intents, key=lambda item: item.order)
    ]


def _binding_updates(outline: OutlinePlan) -> list[SlideAssetBindingUpdate]:
    return [
        SlideAssetBindingUpdate(
            page_order=binding.page_order,
            asset_id=str(binding.asset_id),
            binding_role=binding.binding_role.value
            if hasattr(binding.binding_role, "value")
            else str(binding.binding_role),
            user_description=binding.user_description,
            required=binding.required,
            slide_id=str(binding.slide_id) if binding.slide_id else None,
        )
        for binding in outline.page_asset_bindings
    ]


def _outline_update_from(
    outline: OutlinePlan,
    *,
    sections: list[OutlineSectionUpdate] | None = None,
    page_intents: list[SlideIntentUpdate] | None = None,
) -> OutlineUpdate:
    return OutlineUpdate(
        title=outline.title,
        thesis=outline.thesis,
        audience=outline.audience,
        purpose=outline.purpose,
        target_slide_count=outline.target_slide_count,
        audience_mode=outline.audience_mode.value
        if hasattr(outline.audience_mode, "value")
        else str(outline.audience_mode),
        sections=sections if sections is not None else _section_updates(outline),
        page_intents=page_intents
        if page_intents is not None
        else _intent_updates(list(outline.page_intents)),
        page_asset_bindings=_binding_updates(outline),
        expected_version=outline.version,
    )


def _save_outline(outline_id: UUID, update: OutlineUpdate) -> OutlinePlan:
    with get_session() as session:
        saved = PresentationReviewService(session).update_outline(outline_id, update)
        session.commit()
        return saved


def _bootstrap_intents_from_sections(outline: OutlinePlan) -> list[SlideIntent]:
    intents: list[SlideIntent] = []
    order = 0
    for section in sorted(outline.sections, key=lambda item: item.order):
        if not section.expanded:
            continue
        for _ in range(max(1, section.estimated_slide_count)):
            intents.append(
                SlideIntent(
                    order=order,
                    chapter_id=section.id,
                    page_task=section.purpose or section.title,
                    central_conclusion=section.key_message,
                    required_evidence=list(section.evidence_requirements),
                    required_assets=list(section.required_assets),
                    expected_layout=section.category or "general",
                    notes=section.title,
                )
            )
            order += 1
    return intents


def _ensure_editable_intents(outline: OutlinePlan) -> list[SlideIntent]:
    if outline.page_intents:
        return list(sorted(outline.page_intents, key=lambda item: item.order))
    bootstrapped = _bootstrap_intents_from_sections(outline)
    if not bootstrapped:
        return [
            SlideIntent(
                order=0,
                page_task="待填写页面任务",
                notes="第 1 页",
            )
        ]
    return bootstrapped


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


def _toggle_section_expanded(outline: OutlinePlan, section_id: str) -> None:
    sections = _section_updates(outline)
    updated: list[OutlineSectionUpdate] = []
    for section in sections:
        if section.id == section_id:
            updated.append(
                OutlineSectionUpdate(
                    id=section.id,
                    title=section.title,
                    purpose=section.purpose,
                    key_message=section.key_message,
                    order=section.order,
                    estimated_slide_count=section.estimated_slide_count,
                    evidence_requirements=list(section.evidence_requirements),
                    required_assets=list(section.required_assets),
                    required=section.required,
                    expanded=not section.expanded,
                    category=section.category,
                )
            )
        else:
            updated.append(section)
    _save_outline(outline.id, _outline_update_from(outline, sections=updated))
    st.rerun()


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
            if st.button(
                f"{mark} {section.title} · {section.estimated_slide_count} 页",
                key=f"outline_sec_toggle_{section.id}",
                use_container_width=True,
            ):
                _toggle_section_expanded(outline, section.id)
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


def _persist_intents(outline: OutlinePlan, intents: list[SlideIntent]) -> None:
    reindexed = []
    for index, intent in enumerate(sorted(intents, key=lambda item: item.order)):
        payload = intent.model_copy(deep=True)
        payload.order = index
        reindexed.append(payload)
    _save_outline(
        outline.id,
        _outline_update_from(outline, page_intents=_intent_updates(reindexed)),
    )


def _render_intent_cards(
    cards: list[dict[str, str]],
    *,
    outline: OutlinePlan | None,
    page_picker: bool = False,
) -> None:
    st.markdown("**页面意图卡**")
    if not cards and outline is None:
        st.info("尚无页面意图。先描述汇报任务并生成大纲。")
        return

    mode = st.radio(
        "模式",
        options=["查看", "编辑"],
        horizontal=True,
        key="outline_intent_mode",
    )

    if outline is None:
        st.caption("当前尚无 OutlinePlan，仅可查看规划摘要。")
        mode = "查看"

    selected = int(st.session_state.get("outline_selected_card", 0) or 0)
    intents = _ensure_editable_intents(outline) if outline is not None else []
    source_count = len(intents) if intents else len(cards)
    if source_count <= 0:
        st.info("尚无页面意图。")
        return
    selected = max(0, min(selected, source_count - 1))
    st.session_state.outline_selected_card = selected

    if intents:
        labels = [
            f"{index:02d} {intent.notes.strip() or intent.page_task.strip() or f'第 {index} 页'}"
            for index, intent in enumerate(intents, start=1)
        ]
    else:
        labels = [f"{index:02d} {card['title']}" for index, card in enumerate(cards, start=1)]

    # Wide layout: chapter tree is the only page selector.
    # Narrow layout (or no tree): use a selectbox.
    if page_picker:
        choice = st.selectbox(
            "选择页面",
            options=list(range(source_count)),
            index=selected,
            format_func=lambda value: labels[value] if value < len(labels) else str(value),
            key="outline_card_select",
        )
        st.session_state.outline_selected_card = int(choice)
    else:
        choice = selected
        st.caption(f"当前页面：{labels[choice]}")

    if mode == "查看" or outline is None:
        card = (
            _card_from_slide_intent(intents[int(choice)], title_fallback=f"第 {int(choice) + 1} 页")
            if intents
            else cards[int(choice)]
        )
        with st.container(border=True):
            st.markdown(f"**页面标题**  \n{card['title']}")
            st.markdown(f"**中心结论**  \n{card['conclusion']}")
            st.markdown(f"**页面任务**  \n{card['task']}")
            st.markdown(f"**证据**  \n{card['evidence']}")
            st.markdown(f"**指定素材**  \n{card['assets']}")
            meta = st.columns(2)
            meta[0].markdown(f"**页面类型**  \n{card['page_type']}")
            meta[1].markdown(f"**状态**  \n{card['status']}")
        return

    intent = intents[int(choice)]
    with st.container(border=True):
        title = st.text_input(
            "页面标题",
            value=intent.notes or intent.page_task,
            key=f"outline_intent_title_{outline.id}_{intent.order}",
        )
        conclusion = st.text_area(
            "中心结论",
            value=intent.central_conclusion,
            height=80,
            key=f"outline_intent_conclusion_{outline.id}_{intent.order}",
        )
        task = st.text_area(
            "页面任务",
            value=intent.page_task,
            height=80,
            key=f"outline_intent_task_{outline.id}_{intent.order}",
        )
        evidence = st.text_area(
            "证据（用顿号或换行分隔）",
            value="、".join(intent.required_evidence),
            height=70,
            key=f"outline_intent_evidence_{outline.id}_{intent.order}",
        )
        assets = st.text_area(
            "指定素材（用顿号或换行分隔）",
            value="、".join(intent.required_assets),
            height=70,
            key=f"outline_intent_assets_{outline.id}_{intent.order}",
        )
        page_type_options = list(_PAGE_TYPE_OPTIONS)
        current_type = intent.expected_layout.strip() or "general"
        if current_type not in page_type_options:
            page_type_options = [current_type, *page_type_options]
        page_type = st.selectbox(
            "页面类型",
            options=page_type_options,
            index=page_type_options.index(current_type),
            key=f"outline_intent_type_{outline.id}_{intent.order}",
        )

    actions = st.columns(4)
    with actions[0]:
        if st.button("保存当前页", type="primary", use_container_width=True, key="outline_intent_save"):
            updated = list(intents)
            updated[int(choice)] = SlideIntent(
                order=intent.order,
                chapter_id=intent.chapter_id,
                page_task=(task.strip() or title.strip() or "待填写页面任务")[:500],
                central_conclusion=conclusion.strip()[:1000],
                required_evidence=_split_items(evidence),
                required_assets=_split_items(assets),
                forbidden_content=list(intent.forbidden_content),
                expected_layout=str(page_type),
                notes=(title.strip() or intent.notes)[:2000],
            )
            _persist_intents(outline, updated)
            st.success("已保存当前页意图（生成 Outline Revision）。")
            st.rerun()
    with actions[1]:
        if st.button("复制意图", use_container_width=True, key="outline_intent_copy"):
            cloned = deepcopy(intent)
            cloned.order = len(intents)
            cloned.notes = f"{(cloned.notes or cloned.page_task).strip()}（副本）"
            _persist_intents(outline, [*intents, cloned])
            st.session_state.outline_selected_card = len(intents)
            st.rerun()
    with actions[2]:
        if st.button(
            "删除页面",
            use_container_width=True,
            disabled=len(intents) <= 1,
            key="outline_intent_delete",
        ):
            remaining = [item for index, item in enumerate(intents) if index != int(choice)]
            _persist_intents(outline, remaining)
            st.session_state.outline_selected_card = max(0, int(choice) - 1)
            st.rerun()
    with actions[3]:
        if st.button("插入下一页", use_container_width=True, key="outline_intent_insert"):
            insert_at = int(choice) + 1
            blank = SlideIntent(
                order=insert_at,
                chapter_id=intent.chapter_id,
                page_task="待填写页面任务",
                notes=f"第 {insert_at + 1} 页",
            )
            next_intents = [*intents[:insert_at], blank, *intents[insert_at:]]
            _persist_intents(outline, next_intents)
            st.session_state.outline_selected_card = insert_at
            st.rerun()


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


def _render_draft_banner(document_count: int) -> None:
    if document_count > 0:
        return
    st.warning("无项目证据 · 草稿模式 — 可继续规划与生成，但不得正式交付。")


def _render_default_outline(project_id: UUID, snapshot: PlanningSnapshot) -> None:
    has_mission = snapshot.mission is not None
    has_request = snapshot.presentation_request is not None
    outline, storyline, slides = _load_outline_storyline(project_id)
    cards = _intent_cards_from_sources(outline=outline, snapshot=snapshot, slides=slides)

    try:
        from archium.ui.project_progress_card import load_project_progress_snapshot

        progress = load_project_progress_snapshot()
        _render_draft_banner(int(progress.document_count) if progress else 0)
    except Exception:
        pass

    if not has_mission and not has_request and outline is None and not cards:
        st.info("尚未确认大纲。先描述汇报任务，再生成结构。")
        _render_task_composer(project_id)
        return

    narrow = st.toggle(
        "窄屏布局（用列表选页）",
        value=False,
        key="outline_narrow_layout",
        help="宽屏由左侧章节树选页；窄屏隐藏树，改用页面列表。",
    )
    has_tree = bool(
        (outline is not None and outline.sections)
        or (storyline is not None and storyline.chapters)
        or cards
    )
    # Selectbox only in narrow mode, or when there is nothing for the tree to drive.
    page_picker = narrow or not has_tree

    if narrow:
        _render_intent_cards(cards, outline=outline, page_picker=True)
        with st.expander("汇报任务", expanded=False):
            _render_task_meta(snapshot=snapshot, outline=outline, storyline=storyline)
    else:
        left, mid, right = st.columns([1.05, 1.6, 1.1], gap="medium")
        with left:
            _render_chapter_tree(outline=outline, storyline=storyline, cards=cards)
        with mid:
            _render_intent_cards(cards, outline=outline, page_picker=page_picker)
        with right:
            _render_task_meta(snapshot=snapshot, outline=outline, storyline=storyline)

    st.divider()
    cols = st.columns(2)
    with cols[0]:
        if st.button("重新规划", use_container_width=True, key="outline_replan"):
            project_mission.reset_planning_session()
            st.rerun()
    with cols[1]:
        from archium.application.outline_approval_service import outline_ready_for_approval

        if outline is not None and outline.is_approved:
            st.success(f"大纲已确认（v{outline.version}）")
            if st.button(
                "进入生成 →",
                type="primary",
                use_container_width=True,
                key="outline_goto_generate",
            ):
                st.switch_page(get_app_page("generate"))
        elif outline is None:
            task_ready = has_request or has_mission or bool(cards)
            if not task_ready:
                st.caption("先描述汇报任务，再生成大纲结构。")
            if st.button(
                "确认任务并生成大纲",
                type="primary",
                use_container_width=True,
                disabled=not task_ready,
                key="outline_confirm_task",
            ):
                task = (
                    st.session_state.get("outline_task_draft")
                    or st.session_state.get("mission_task_draft")
                    or ""
                )
                if not str(task).strip() and snapshot.presentation_request is not None:
                    req = snapshot.presentation_request
                    task = (
                        getattr(req, "core_message", None)
                        or getattr(req, "purpose", None)
                        or getattr(req, "user_notes", None)
                        or getattr(req, "title", None)
                        or ""
                    )
                if not str(task).strip() and snapshot.mission is not None:
                    task = getattr(snapshot.mission, "description", "") or ""
                if not str(task).strip():
                    st.warning("请先填写任务描述。")
                else:
                    st.session_state.mission_task_draft = str(task)
                    project_mission.start_outline_planning(project_id, str(task))
        else:
            can_confirm, missing = outline_ready_for_approval(outline)
            if not can_confirm:
                st.caption("确认大纲前还需：" + "；".join(missing))
            if st.button(
                "确认大纲并开始生成 →",
                type="primary",
                use_container_width=True,
                disabled=not can_confirm,
                key="outline_confirm",
            ):
                _confirm_outline_and_go(project_id, outline=outline)

    if not has_request and has_mission:
        with st.expander("继续完善任务描述", expanded=False):
            _render_task_composer(project_id)


def _confirm_outline_and_go(project_id: UUID, *, outline: OutlinePlan | None) -> None:
    from archium.application.outline_approval_service import OutlineApprovalService
    from archium.exceptions import WorkflowError
    from archium.ui.error_handlers import format_user_error

    try:
        with get_session() as session:
            result = OutlineApprovalService(session).approve_for_project(
                project_id,
                approved_by="user",
                expected_revision=outline.version if outline is not None else None,
            )
            session.commit()
        records = list(st.session_state.get("outline_approval_records") or [])
        records.append(
            {
                "outline_id": str(result.outline_id) if result.outline_id else None,
                "presentation_id": str(result.presentation_id)
                if result.presentation_id
                else None,
                "status": result.approval_status,
                "revision": result.approved_revision,
                "hash": result.outline_hash,
                "by": result.approved_by,
                "at": result.approved_at.isoformat(),
            }
        )
        st.session_state.outline_approval_records = records[-20:]
        if result.presentation_id is not None:
            st.session_state.selected_presentation_id = str(result.presentation_id)
        st.success(result.message)
        st.switch_page(get_app_page("generate"))
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def render() -> None:
    render_stage_header("outline")
    st.caption("确认章节、页面意图与汇报任务。高级六步规划可按需打开。")

    project_id = render_flow_project_context(allow_create=False, key_prefix="outline")
    if project_id is None:
        render_stage_nav("outline", include_next=False)
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

    # Outline owns the confirm CTA — do not render a second「前往生成」.
    render_stage_nav("outline", include_next=False)
