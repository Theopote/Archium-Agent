"""Unit tests for Showcase Case 001 + investor score gate."""

from __future__ import annotations

import json

from archium.application.visual.showcase_case_001 import (
    CASE_001_DEFAULT_PRESET,
    CASE_001_ID,
    DEMO_TOUR_TITLES,
    assert_case_001_rhythm,
    load_case_001_manifest,
    load_case_001_outline,
    plan_case_001_composition,
    scorecard_template,
    showcase_case_001_dir,
)
from archium.domain.visual.showcase_score import (
    SHOWCASE_GATE_AESTHETIC_MIN,
    SHOWCASE_GATE_PROFESSIONALISM_MIN,
    SHOWCASE_GATE_TOTAL_MIN,
    ShowcaseInvestorDimensions,
    ShowcaseInvestorScore,
    empty_showcase_score,
    showcase_score_from_dict,
)


class TestShowcaseInvestorScore:
    def test_incomplete_fails_gate(self) -> None:
        score = empty_showcase_score(CASE_001_ID)
        gate = score.evaluate_gate()
        assert gate.complete is False
        assert gate.passed is False
        assert gate.failures[0].startswith("incomplete_scores:")

    def test_pass_gate_at_threshold(self) -> None:
        score = ShowcaseInvestorScore(
            case_id=CASE_001_ID,
            style_preset_id=CASE_001_DEFAULT_PRESET,
            dimensions=ShowcaseInvestorDimensions(
                information_logic=7,
                architectural_expression=7,
                aesthetic=7,
                professionalism=7,
                editability_studio=7,
            ),
        )
        assert score.total == 35
        gate = score.evaluate_gate()
        assert gate.passed is True
        assert gate.failures == []

    def test_fail_when_aesthetic_below_seven(self) -> None:
        score = ShowcaseInvestorScore(
            case_id=CASE_001_ID,
            dimensions=ShowcaseInvestorDimensions(
                information_logic=9,
                architectural_expression=9,
                aesthetic=6,
                professionalism=9,
                editability_studio=9,
            ),
        )
        gate = score.evaluate_gate()
        assert gate.total == 42
        assert gate.passed is False
        assert any("aesthetic" in item for item in gate.failures)

    def test_fail_when_total_below_thirty_five(self) -> None:
        score = ShowcaseInvestorScore(
            case_id=CASE_001_ID,
            dimensions=ShowcaseInvestorDimensions(
                information_logic=6,
                architectural_expression=6,
                aesthetic=7,
                professionalism=7,
                editability_studio=6,
            ),
        )
        assert score.total == 32
        gate = score.evaluate_gate()
        assert gate.passed is False
        assert any("total<" in item for item in gate.failures)

    def test_template_json_roundtrip(self) -> None:
        template_path = showcase_case_001_dir() / "scorecard.template.json"
        raw = json.loads(template_path.read_text(encoding="utf-8"))
        score = showcase_score_from_dict(
            {
                "case_id": raw["case_id"],
                "schema_version": raw["schema_version"],
                "style_preset_id": raw.get("style_preset_id"),
                "dimensions": raw["dimensions"],
            }
        )
        assert score.case_id == CASE_001_ID
        assert score.is_complete is False


class TestShowcaseCase001:
    def test_pack_files_exist(self) -> None:
        root = showcase_case_001_dir()
        assert (root / "manifest.json").is_file()
        assert (root / "outline.json").is_file()
        assert (root / "scorecard.template.json").is_file()
        assert (root / "fixtures" / "site-brief.txt").is_file()

    def test_manifest_gate_matches_domain(self) -> None:
        manifest = load_case_001_manifest()
        assert manifest["case_id"] == CASE_001_ID
        assert manifest["style_preset_id"] == CASE_001_DEFAULT_PRESET
        gate = manifest["gate"]
        assert gate["total_min"] == SHOWCASE_GATE_TOTAL_MIN
        assert gate["aesthetic_min"] == SHOWCASE_GATE_AESTHETIC_MIN
        assert gate["professionalism_min"] == SHOWCASE_GATE_PROFESSIONALISM_MIN

    def test_outline_demo_tour_and_rhythm(self) -> None:
        outline = load_case_001_outline()
        assert len(outline) == 20
        titles = {row["title"] for row in outline}
        for title in DEMO_TOUR_TITLES:
            assert title in titles
        plan = plan_case_001_composition(outline=outline)
        snapshot = assert_case_001_rhythm(plan)
        assert snapshot["slide_count"] == 20
        assert snapshot["peak_count"] <= snapshot["climax_budget"]

    def test_scorecard_template_helper(self) -> None:
        payload = scorecard_template()
        assert payload["schema_version"] == "showcase_investor_score_v1"
        assert payload["gate"]["total_min"] == 35

    def test_render_bundle_and_dry_run(self, tmp_path) -> None:  # noqa: ANN001
        from archium.application.visual.showcase_case_001 import (
            build_case_001_render_bundle,
            write_case_001_dry_run,
        )

        bundle = build_case_001_render_bundle()
        assert len(bundle.plans) == 20
        assert bundle.style_preset_id == CASE_001_DEFAULT_PRESET
        assert all(plan.elements for plan in bundle.plans)
        # Demo tour slides present with expected families bias.
        titles = [slide.title for slide in bundle.slides]
        for title in DEMO_TOUR_TITLES:
            assert title in titles

        summary = write_case_001_dry_run(bundle, output_dir=tmp_path)
        assert summary["mode"] == "dry_run"
        assert summary["slide_count"] == 20
        assert (tmp_path / "presentation.layout_instructions.json").is_file()
        assert (tmp_path / "rhythm_snapshot.json").is_file()
        assert len(list((tmp_path / "layout_plans").glob("slide_*.json"))) == 20

        deck = json.loads(
            (tmp_path / "presentation.layout_instructions.json").read_text(
                encoding="utf-8"
            )
        )
        assert len(deck.get("slides") or deck.get("pages") or []) >= 20 or (
            isinstance(deck, dict) and "slides" in deck
        )