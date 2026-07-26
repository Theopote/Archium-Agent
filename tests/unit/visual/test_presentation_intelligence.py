"""Presentation Intelligence + Case 001 designer-product tightening."""

from __future__ import annotations

import json

from archium.application.visual.page_direction_service import PageDirectionService
from archium.application.visual.presentation_intelligence_service import (
    PresentationIntelligenceService,
)
from archium.application.visual.showcase_case_001 import (
    CASE_001_DEFAULT_PRESET,
    CASE_001_ID,
    DEMO_TOUR_TITLES,
    build_case_001_deck,
    build_case_001_render_bundle,
    case_001_design_system,
    write_case_001_dry_run,
)
from archium.domain.visual.enums import LayoutFamily


class TestPresentationIntelligence:
    def test_brief_from_case_001(self) -> None:
        bundle = build_case_001_render_bundle()
        brief = PresentationIntelligenceService().build_brief(
            style_preset_id=bundle.style_preset_id,
            slides=bundle.slides,
            intents=bundle.intents,
            composition=bundle.composition,
            case_id=CASE_001_ID,
            demo_tour_titles=list(DEMO_TOUR_TITLES),
        )
        assert brief.project_personality
        assert brief.style_preset_id == CASE_001_DEFAULT_PRESET
        assert brief.narrative_logic == "evidence_first"
        assert brief.content_policy_summary
        assert brief.page_direction_hits == 20
        assert brief.density_min is not None and brief.density_max is not None
        assert brief.density_max > brief.density_min
        assert len(brief.emotional_curve) == 20
        assert any("气质" in item for item in brief.first_impression_checks)

    def test_circulation_conflict_director_tightens_copy(self) -> None:
        slides, intents = build_case_001_deck()
        conflict = next(s for s in slides if s.title == "流线冲突")
        intent = next(i for i in intents if i.slide_id == conflict.id)
        direction = PageDirectionService().direct(conflict, existing_intent=intent)
        assert direction.situation_rule_id == "site_traffic_conflict"
        assert direction.copy_budget.max_key_points <= 1
        assert LayoutFamily.TEXTUAL_ARGUMENT in direction.forbidden_layout_families

        directed = PageDirectionService().apply_to_intent(intent, direction)
        clipped = PresentationIntelligenceService().clip_slide_copy(conflict, directed)
        assert len(clipped.key_points) <= 1

    def test_case_001_render_applies_director(self) -> None:
        bundle = build_case_001_render_bundle()
        conflict_idx = next(
            i for i, s in enumerate(bundle.slides) if s.title == "流线冲突"
        )
        intent = bundle.intents[conflict_idx]
        assert intent.page_direction is not None
        assert intent.page_direction.situation_rule_id == "site_traffic_conflict"
        assert intent.page_direction.narrative_emotion.value == "problem"
        assert intent.emotional_tone == "problem"
        assert intent.page_direction.claim
        # Forbidden textual argument → evidence/analytical preferred.
        assert LayoutFamily.TEXTUAL_ARGUMENT not in intent.preferred_layout_families
        assert len(bundle.slides[conflict_idx].key_points) <= 1

    def test_preset_contrast_measurable(self) -> None:
        technical = case_001_design_system("architecture_technical")
        minimal = case_001_design_system("architecture_minimal")
        # Minimal is spacier / larger hero threshold than technical.
        assert minimal.page.margin_left > technical.page.margin_left
        assert (
            minimal.thresholds.min_hero_area_ratio
            >= technical.thresholds.min_hero_area_ratio
        )
        assert (
            minimal.thresholds.min_whitespace_ratio
            >= technical.thresholds.min_whitespace_ratio
        )

        tech_bundle = build_case_001_render_bundle(
            style_preset_id="architecture_technical"
        )
        mini_bundle = build_case_001_render_bundle(
            style_preset_id="architecture_minimal"
        )
        assert (
            tech_bundle.design.page.margin_left != mini_bundle.design.page.margin_left
        )

    def test_dry_run_writes_intelligence_json(self, tmp_path) -> None:  # noqa: ANN001
        bundle = build_case_001_render_bundle()
        summary = write_case_001_dry_run(bundle, output_dir=tmp_path)
        assert (tmp_path / "presentation_intelligence.json").is_file()
        assert (tmp_path / "page_claims.json").is_file()
        claims = json.loads((tmp_path / "page_claims.json").read_text(encoding="utf-8"))
        assert claims["product_label"] == "页主张"
        conflict = next(p for p in claims["pages"] if p["title"] == "流线冲突")
        assert conflict["emotion"] == "problem"
        assert conflict["evidence_priority"][0] == "site_photo"
        assert conflict["visual_concept"]["visual_metaphor"] == "fragment_to_network"
        assert summary["page_direction_hits"] == 20
        assert "site_traffic_conflict" in summary["situation_rules_fired"]
