"""UI hygiene: selection SSOT, ST-003 proposal-only path, resume UX copy."""

from __future__ import annotations

from pathlib import Path

from archium.exceptions import WorkflowError
from archium.ui.workflow_resume_ux import (
    RESUME_EXPORT_BUTTON_LABEL,
    is_no_checkpoint_resume_error,
)


def test_comment_inbox_uses_set_studio_selection() -> None:
    source = Path("archium/ui/studio/comment_inbox_panel.py").read_text(encoding="utf-8")
    assert "set_studio_selection" in source
    focus_fn = source.split("def _focus_comment_on_canvas")[1].split("def _render_snapshot_diff")[0]
    assert 'st.session_state["studio_selected_element_id"]' not in focus_fn
    assert 'st.session_state["studio_selected_element_ids"]' not in focus_fn


def test_ai_workspace_no_direct_edit_bypass_when_scene_path() -> None:
    source = Path("archium/ui/studio/ai_workspace_panel.py").read_text(encoding="utf-8")
    assert "版式直接编辑" not in source
    assert "ST-003" in source
    # Legacy direct apply only in no-Scene helper
    assert "def _render_legacy_panel" in source
    proposal_branch = source.split("if slide_snapshot.render_scene is None:")[1]
    # After the no-scene early return, main path must create proposals
    assert "生成修改提案" in proposal_branch
    assert "create_slide_scene_proposal_from_text" in proposal_branch


def test_studio_guide_matches_inspector_tab_name() -> None:
    guide = Path("docs/studio-user-guide.md").read_text(encoding="utf-8")
    assert "属性|布局|内容|修改|评论|风格|检查" in guide
    assert "属性|布局|内容|AI|评论|风格|检查" not in guide
    assert "**工作室** → **修改**" in guide


def test_is_no_checkpoint_resume_error() -> None:
    assert is_no_checkpoint_resume_error(
        WorkflowError("Workflow run x 无可恢复的 interrupt/checkpoint（WF-004）")
    )
    assert not is_no_checkpoint_resume_error(WorkflowError("LLM timeout"))


def test_resume_button_label_is_product_facing() -> None:
    assert "审核门" in RESUME_EXPORT_BUTTON_LABEL
    review = Path("archium/ui/review_panel.py").read_text(encoding="utf-8")
    workspace = Path("archium/ui/pages/workspace.py").read_text(encoding="utf-8")
    assert "RESUME_EXPORT_BUTTON_LABEL" in review
    assert "RESUME_EXPORT_BUTTON_LABEL" in workspace
    assert "重试工作流导出" not in review
    assert "重试工作流导出" not in workspace


def test_export_panel_offers_working_draft_when_formal_blocked() -> None:
    export = Path("archium/ui/studio/export_panel.py").read_text(encoding="utf-8")
    assert "require_formal_gate" in export
    assert "导出工作稿" in export
    assert "select_presentation" in Path("archium/ui/pages/flow/generate.py").read_text(
        encoding="utf-8"
    )


def test_art_direction_panel_leads_with_presentation_intelligence() -> None:
    source = Path("archium/ui/art_direction_panel.py").read_text(encoding="utf-8")
    assert "汇报气质" in source
    assert "Presentation Intelligence" in source
    assert "事务所气质（Style Preset）" in source
    assert "工程细节（令牌策略原文）" in source
    # Preset selectbox must sit outside the form so personality updates live.
    form_idx = source.index('with st.form(f"art_direction_form_')
    preset_idx = source.index("事务所气质（Style Preset）")
    assert preset_idx < form_idx


def test_generate_page_exposes_showcase_case_001_rehearsal() -> None:
    generate = Path("archium/ui/pages/flow/generate.py").read_text(encoding="utf-8")
    panel = Path("archium/ui/showcase_case_001_panel.py").read_text(encoding="utf-8")
    assert "render_showcase_case_001_panel" in generate
    assert "Showcase 排练：Case 001" in panel
    assert "fragment_to_network" in panel


def test_studio_style_tab_surfaces_art_direction() -> None:
    studio = Path("archium/ui/pages/studio.py").read_text(encoding="utf-8")
    assert "_render_studio_art_direction" in studio
    assert 'render_inspector_section("汇报气质")' in studio
    props = Path("archium/ui/studio/slide_properties.py").read_text(encoding="utf-8")
    assert "页主张" in props
    assert "as_page_claim" in props
