"""Knowledge gap detection — project-type aware required keys."""

from __future__ import annotations

from uuid import uuid4

from archium.application.knowledge_gap_detection import (
    detect_knowledge_gaps,
    resolve_required_fact_keys,
)


def test_resolve_required_fact_keys_excludes_bed_count_for_temple() -> None:
    keys = resolve_required_fact_keys(
        facts=[],
        project_name="陕西三原县清凉寺重建",
        project_description="原址重建寺庙",
    )
    assert "bed_count" not in keys
    assert "plot_ratio" not in keys
    assert "location" in keys
    assert "main_function" in keys


def test_lightweight_mode_uses_minimal_keys() -> None:
    keys = resolve_required_fact_keys(
        facts=[],
        project_name="某综合体",
        lightweight=True,
    )
    assert keys == ("project_name", "location", "main_function")


def test_lightweight_mode_skips_blocking_missing_metrics() -> None:
    project_id = uuid4()
    report = detect_knowledge_gaps(
        project_id,
        facts=[],
        required_fact_keys=("plot_ratio", "bed_count"),
        lightweight_mode=True,
    )
    assert report.gap_count == 2
    assert report.blocking_gaps == []


def test_project_entity_name_satisfies_project_name_gap() -> None:
    project_id = uuid4()
    report = detect_knowledge_gaps(
        project_id,
        facts=[],
        required_fact_keys=("project_name", "location", "main_function"),
        project_name="滨江城市客厅文化中心",
    )
    assert all(gap.related_keys != ("project_name",) for gap in report.gaps)
    assert {gap.description for gap in report.gaps} == {
        "缺少标准事实：项目位置",
        "缺少标准事实：主要功能",
    }


def test_filter_unknowns_satisfied_by_known_drops_answered_labels() -> None:
    from archium.application.knowledge_gap_detection import filter_unknowns_satisfied_by_known

    kept = filter_unknowns_satisfied_by_known(
        [
            "缺少标准事实：项目名称",
            "缺少标准事实：项目位置",
            "缺少标准事实：甲方",
        ],
        known={
            "name": "滨江城市客厅文化中心",
            "location": "杭州市滨江区",
        },
    )
    assert kept == ["缺少标准事实：甲方"]
