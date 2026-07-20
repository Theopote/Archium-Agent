"""E2E Benchmark quality gate case definitions (M5).

Nightly gates (see ``test_e2e_pipeline_gate.py`` and ``test_e2e_quality_gate.py``):

- **Pipeline Gate** (``e2e_pipeline``): deliverable chain runs with validation bypass.
- **Quality Gate** (``e2e_quality``): real ``LayoutValidationService`` scoring only.
"""

from __future__ import annotations

from archium.domain.visual.e2e_benchmark import (
    E2EBenchmarkCase,
    E2EContentExpectation,
    E2EExpectedOutcomes,
    E2EHeroAssetExpectation,
)

# Canonical nightly gate: content planning → visual workflow → PPTX → screenshots.
E2E_QUALITY_GATE_CASE_ID = "quality_gate_project_proposal"

QUALITY_GATE_PROJECT_PROPOSAL = E2EBenchmarkCase(
    case_id=E2E_QUALITY_GATE_CASE_ID,
    scenario="project_proposal",
    title="老院区更新概念汇报",
    description="Nightly quality gate: DOCX import through deliverable export.",
    task_description="根据任务书制作交通改造汇报",
    input_documents=["source.docx"],
    input_images=["hero_candidate.png"],
    enable_content_planning=True,
    enable_visual_workflow=True,
    enable_pptx_export=True,
    enable_screenshot_check=True,
    difficulty="medium",
    tags=["quality_gate", "nightly"],
    expected_outcomes=E2EExpectedOutcomes(
        min_slide_count=4,
        max_slide_count=4,
        content_expectations=E2EContentExpectation(
            required_keywords=["交通", "改造"],
        ),
        hero_asset_expectations=E2EHeroAssetExpectation(
            min_usage_ratio=0.0,
            max_reuse_count=3,
        ),
        min_rule_pass_rate=0.75,
        min_avg_layout_score=0.70,
        min_deck_qa_score=0.60,
    ),
)

E2E_QUALITY_GATE_CASES: tuple[E2EBenchmarkCase, ...] = (QUALITY_GATE_PROJECT_PROPOSAL,)

E2E_QUALITY_GATE_MIN_PASS_RATE = 1.0
