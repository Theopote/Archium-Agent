"""Gap-fill tests: split proposal, skill audit, theme impact model."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.agent_skills.audit_store import SkillAuditStore
from archium.config.settings import Settings
from archium.domain.agent_skill import SkillInvocationAudit
from archium.domain.slide import SlideSpec
from archium.domain.slide_split import (
    SlideSplitPagePreview,
    SlideSplitPlan,
    SlideSplitProposal,
)
from archium.domain.visual.theme_change_proposal import ThemeDeckImpactStats


def test_theme_deck_impact_stats_fields() -> None:
    stats = ThemeDeckImpactStats(
        affected_pages=24,
        font_changes=24,
        background_changes=8,
        drawing_node_changes=0,
        evidence_photo_changes=0,
        warnings=3,
        blockers=0,
    )
    assert stats.affected_pages == 24
    assert stats.blockers == 0


def test_slide_split_proposal_before_after() -> None:
    source_id = uuid4()
    slide_a = SlideSpec.model_construct(
        id=source_id,
        presentation_id=uuid4(),
        chapter_id="c",
        order=0,
        title="A",
        message="m",
        key_points=["1", "2", "3", "4"],
    )
    slide_b = SlideSpec.model_construct(
        id=uuid4(),
        presentation_id=slide_a.presentation_id,
        chapter_id="c",
        order=1,
        title="B",
        message="m2",
        key_points=["3", "4"],
    )
    plan = SlideSplitPlan(
        reason="overloaded",
        source_slide_id=source_id,
        new_slides=[slide_a, slide_b],
    )
    proposal = SlideSplitProposal(
        source_slide_id=source_id,
        plan=plan,
        before=SlideSplitPagePreview(title="A", key_points=["1", "2", "3", "4"]),
        after=[
            SlideSplitPagePreview(title="A", key_points=["1", "2"]),
            SlideSplitPagePreview(title="B", key_points=["3", "4"]),
        ],
        capacity_status="overloaded",
    )
    assert proposal.status == "draft"
    assert len(proposal.after) == 2


def test_skill_audit_store_writes_jsonl(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, project_storage_path=tmp_path)
    store = SkillAuditStore(settings)
    audit = SkillInvocationAudit(
        task_type="layout_plan",
        skill_ids=["drawing-page-design"],
        skill_versions=["1.0.0"],
        skill_checksums=["abc"],
        prompt_uris=["skill://drawing"],
    )
    project_id = uuid4()
    path = store.record(audit, project_id=project_id, presentation_id=uuid4())
    assert path is not None
    assert path.is_file()
    line = path.read_text(encoding="utf-8").strip()
    assert "drawing-page-design" in line
    assert "layout_plan" in line
