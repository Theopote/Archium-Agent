"""Smoke imports for Presentation Studio UI modules."""


def test_studio_modules_import() -> None:
    from archium.application.visual.deck_repair_service import DeckRepairService
    from archium.ui.studio import (
        ai_edit_panel,
        content_adaptation_panel,
        deck_repair_panel,
        element_labels,
        export_panel,
        history_panel,
        human_review_panel,
        layout_candidates_panel,
        onboarding_panel,
        project_sidebar,
        slide_actions,
        slide_canvas,
        slide_navigator,
        slide_properties,
    )
    from archium.ui.studio_service import (
        apply_deck_repair_suggestion,
        apply_slide_edit_command,
        create_studio_project,
        reorder_studio_slide,
    )

    assert DeckRepairService is not None
    assert apply_deck_repair_suggestion is not None
    assert apply_slide_edit_command is not None
    assert create_studio_project is not None
    assert reorder_studio_slide is not None
    assert export_panel.render_export_panel is not None
    assert export_panel.render_studio_toolbar is not None
    assert deck_repair_panel.render_deck_repair_panel is not None
    assert human_review_panel.render_human_review_panel is not None
    assert onboarding_panel.render_studio_onboarding is not None
    assert element_labels.format_element_label is not None
    for module in (
        ai_edit_panel,
        content_adaptation_panel,
        history_panel,
        layout_candidates_panel,
        project_sidebar,
        slide_actions,
        slide_canvas,
        slide_navigator,
        slide_properties,
    ):
        assert module is not None
