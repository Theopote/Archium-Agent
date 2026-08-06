"""Product QA bucket mapping tests."""

from __future__ import annotations

from archium.domain.product_qa_bucket import (
    ProductQaBucket,
    collect_product_qa_from_sources,
    group_product_qa_findings,
    product_qa_bucket_for_code,
)


def test_fact_codes_map_to_fact_bucket() -> None:
    assert product_qa_bucket_for_code("EVIDENCE.MISSING_CITATION") == ProductQaBucket.FACT
    assert product_qa_bucket_for_code("CONTENT.METRIC_MISSING_UNIT") == ProductQaBucket.FACT
    assert product_qa_bucket_for_code("SEMANTIC.EXTERNAL_FACT_WITHOUT_CITATION") == ProductQaBucket.FACT
    assert product_qa_bucket_for_code("ARCH.INCONSISTENT_AREA_UNITS") == ProductQaBucket.FACT


def test_expression_codes_map_to_expression_bucket() -> None:
    assert product_qa_bucket_for_code("CRITIC.WEAK_HIERARCHY") == ProductQaBucket.EXPRESSION
    assert product_qa_bucket_for_code("IMAGE_TEXT.NO_DIRECT_RELATION") == ProductQaBucket.EXPRESSION
    assert product_qa_bucket_for_code("LAYOUT.HIGH_TEXT_DENSITY") == ProductQaBucket.EXPRESSION
    assert product_qa_bucket_for_code("ARCH.FLOW_DIAGRAM_MISSING_LEGEND") == ProductQaBucket.EXPRESSION
    assert product_qa_bucket_for_code("DECK.NO_ADVANCEMENT") == ProductQaBucket.EXPRESSION


def test_render_codes_map_to_render_bucket() -> None:
    assert product_qa_bucket_for_code("POST_RENDER.IMAGE_NOT_LOADED") == ProductQaBucket.RENDER
    assert product_qa_bucket_for_code("LAYOUT.TEXT_OVERFLOW") == ProductQaBucket.RENDER
    assert product_qa_bucket_for_code("EDIT.PPTX_MISALIGNED") == ProductQaBucket.RENDER
    assert product_qa_bucket_for_code("SEMANTIC.SCENE_PPTX_NODE_MISMATCH") == ProductQaBucket.RENDER
    assert product_qa_bucket_for_code("LAYOUT.FONT_SUBSTITUTION") == ProductQaBucket.RENDER


def test_group_product_qa_findings_orders_three_buckets() -> None:
    findings = collect_product_qa_from_sources(
        review_issues=[
            {"rule_code": "EVIDENCE.MISSING_CITATION", "title": "缺引用"},
            {"rule_code": "LAYOUT.HIGH_TEXT_DENSITY", "title": "文字过多"},
            {"rule_code": "POST_RENDER.BLANK_PAGE", "title": "空白页"},
        ]
    )
    summaries = group_product_qa_findings(findings)
    assert [item.bucket for item in summaries] == [
        ProductQaBucket.FACT,
        ProductQaBucket.EXPRESSION,
        ProductQaBucket.RENDER,
    ]
    assert [item.count for item in summaries] == [1, 1, 1]
    assert summaries[0].label == "事实 QA"
    assert summaries[1].label == "表达 QA"
    assert summaries[2].label == "渲染 QA"


def test_collect_merges_deck_and_critic() -> None:
    findings = collect_product_qa_from_sources(
        deck_qa_report={
            "findings": [
                {"rule_code": "DECK.DUPLICATE_MESSAGE", "message": "叙事重复", "severity": "warning"}
            ]
        },
        critic_report={
            "findings": [
                {"rule_code": "CRITIC.NO_FOCUS", "message": "主次不清", "severity": "major"}
            ]
        },
        quality_issues=[
            {"code": "EDIT.TEXT_NOT_EDITABLE", "message": "文字不可编辑", "severity": "major"}
        ],
    )
    buckets = {item.bucket for item in findings}
    assert ProductQaBucket.EXPRESSION in buckets
    assert ProductQaBucket.RENDER in buckets
    assert len(findings) == 3


def test_group_collapses_repeated_rule_codes() -> None:
    findings = collect_product_qa_from_sources(
        critic_report={
            "findings": [
                {
                    "rule_code": "CRITIC.FOCUS_UNCLEAR",
                    "message": "主次不清",
                    "severity": "warning",
                }
                for _ in range(120)
            ]
            + [
                {
                    "rule_code": "CRITIC.TENSION_FLAT",
                    "message": "节奏偏平",
                    "severity": "info",
                }
                for _ in range(80)
            ]
        }
    )
    summaries = group_product_qa_findings(findings)
    expression = next(item for item in summaries if item.bucket == ProductQaBucket.EXPRESSION)
    assert expression.count == 2
    assert "120 处" in expression.findings[0].title
