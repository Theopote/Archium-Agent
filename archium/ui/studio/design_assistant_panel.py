"""Unified Design Assistant — scores, findings, and quick actions for Studio."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import streamlit as st

from archium.ui.studio.page_ai_suggestions import page_partner_suggestions
from archium.ui.visual_service import SlideVisualSnapshot


@dataclass(frozen=True)
class AssistantFinding:
    message: str
    severity: str
    action_label: str | None = None
    action_prompt: str | None = None


@dataclass(frozen=True)
class AssistantQuickAction:
    label: str
    prompt: str


DEFAULT_QUICK_ACTIONS: tuple[AssistantQuickAction, ...] = (
    AssistantQuickAction("扩大主图", "放大主视觉元素，增强页面视觉中心"),
    AssistantQuickAction("减少文字", "减少本页文字，保留单一核心结论"),
    AssistantQuickAction("优化层级", "调整标题与正文层级，让信息主次更分明"),
)


def collect_assistant_findings(slide_snapshot: SlideVisualSnapshot | None) -> list[AssistantFinding]:
    if slide_snapshot is None:
        return []

    findings: list[AssistantFinding] = []
    validation = slide_snapshot.validation
    if validation is not None and validation.issues:
        for issue in validation.issues[:4]:
            prompt = None
            message_lower = issue.message.lower()
            if "overflow" in message_lower or "溢出" in issue.message:
                prompt = "修复文字溢出，必要时缩短正文"
            elif "hero" in message_lower or "主视觉" in issue.message:
                prompt = "放大主视觉元素，增强页面视觉中心"
            findings.append(
                AssistantFinding(
                    message=issue.message,
                    severity=issue.severity.value,
                    action_label="修复" if prompt else None,
                    action_prompt=prompt,
                )
            )

    critic = slide_snapshot.visual_critic
    if isinstance(critic, dict):
        for item in (critic.get("findings") or [])[:4]:
            if not isinstance(item, dict):
                continue
            message = str(item.get("message") or "").strip()
            if not message:
                continue
            suggestion = str(item.get("suggestion") or "").strip()
            findings.append(
                AssistantFinding(
                    message=message,
                    severity=str(item.get("severity") or "warning"),
                    action_label="应用建议" if suggestion else None,
                    action_prompt=suggestion or None,
                )
            )

    slide = slide_snapshot.slide
    for tip in page_partner_suggestions(slide):
        findings.append(
            AssistantFinding(
                message=tip,
                severity="info",
                action_label=_tip_action_label(tip),
                action_prompt=_tip_action_prompt(tip),
            )
        )

    return _dedupe_findings(findings)[:8]


def _tip_action_label(tip: str) -> str | None:
    if "信息过多" in tip or "减少文字" in tip:
        return "减少文字"
    if "剖面" in tip or "流线" in tip or "关系图" in tip:
        return "加分析图"
    if "叙事偏空" in tip or "页意图" in tip:
        return "补页意图"
    return None


def _tip_action_prompt(tip: str) -> str | None:
    if "信息过多" in tip:
        return "减少本页文字，保留单一核心结论"
    if "叙事偏空" in tip:
        return "补充本页核心结论与关键论据"
    if "剖面" in tip or "流线" in tip or "关系图" in tip:
        return "为本页增加剖面、流线或关系分析图，减少装饰性图片"
    if "SlideRole" in tip or "页角色" in tip:
        return None
    return None


def _dedupe_findings(items: list[AssistantFinding]) -> list[AssistantFinding]:
    seen: set[str] = set()
    unique: list[AssistantFinding] = []
    for item in items:
        key = item.message.strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _page_score(slide_snapshot: SlideVisualSnapshot | None) -> int | None:
    from archium.ui.studio.page_intelligence_strip import build_page_intelligence

    intel = build_page_intelligence(slide_snapshot)
    return intel.score if intel is not None else None


def open_modify_with_prompt(slide_id: UUID, prompt: str) -> None:
    st.session_state.studio_show_inspector = True
    st.session_state.studio_inspector_expanded = True
    st.session_state.studio_inspector_tab = "修改"
    st.session_state[f"studio_ai_edit_input_{slide_id}"] = prompt


def render_design_assistant_panel(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
) -> None:
    """Primary right-rail panel: score, findings, and quick actions."""
    st.markdown("**设计助理**")
    if slide_snapshot is None:
        st.caption("选择一页后，这里显示视觉评分、问题与可执行建议。")
        return

    from archium.ui.studio.element_intent_panel import render_element_intent_panel

    has_selection = render_element_intent_panel(slide_snapshot=slide_snapshot)
    if has_selection:
        st.divider()

    slide_id = slide_snapshot.slide.id
    score = _page_score(slide_snapshot)
    if score is not None:
        st.metric("视觉评分", f"{score}/100")
    else:
        st.caption("生成版式后将显示视觉评分。")

    findings = collect_assistant_findings(slide_snapshot)
    if findings:
        st.markdown("**发现**")
        for index, finding in enumerate(findings):
            st.markdown(f"- {finding.message}")
            if finding.action_label and finding.action_prompt and st.button(
                finding.action_label,
                key=f"studio_assist_action_{slide_id}_{index}",
                use_container_width=True,
            ):
                open_modify_with_prompt(slide_id, finding.action_prompt)
                st.rerun()
    else:
        st.caption("本页结构尚可 — 暂无强制建议。")

    st.markdown("**快捷操作**")
    action_cols = st.columns(3)
    for index, action in enumerate(DEFAULT_QUICK_ACTIONS):
        with action_cols[index % 3]:
            if st.button(
                action.label,
                key=f"studio_quick_{slide_id}_{index}",
                use_container_width=True,
            ):
                open_modify_with_prompt(slide_id, action.prompt)
                st.rerun()

    if st.button(
        "打开修改提案",
        key=f"studio_open_modify_{slide_id}",
        use_container_width=True,
    ):
        st.session_state.studio_show_inspector = True
        st.session_state.studio_inspector_expanded = True
        st.session_state.studio_inspector_tab = "修改"
        st.rerun()
