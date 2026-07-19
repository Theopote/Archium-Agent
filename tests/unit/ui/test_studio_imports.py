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
        layout_candidates_panel,
        project_sidebar,
        slide_actions,
        slide_canvas,
        slide_navigator,
        slide_properties,
    )
    from archium.ui.studio_service import apply_deck_repair_suggestion

    assert DeckRepairService is not None
    assert apply_deck_repair_suggestion is not None
    assert export_panel.render_export_panel is not None
    assert deck_repair_panel.render_deck_repair_panel is not None
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
