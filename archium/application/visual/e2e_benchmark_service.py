"""End-to-End Benchmark Service.

执行完整的端到端验证：
1. 模拟用户导入文档和素材
2. 让系统自主完成所有决策（不预先指定 LayoutFamily/素材/Variant）
3. 评估最终输出质量
4. 对比期望标准
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.ingestion_service import IngestionService
from archium.application.visual.deck_qa_service import DeckQAService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.visual.e2e_benchmark import (
    E2EBenchmarkCase,
    E2EBenchmarkResult,
    E2EBenchmarkSummary,
    E2EContentCoverageResult,
    E2EContentExpectation,
    E2EHeroAssetExpectation,
    E2EHeroAssetResult,
    E2ELayoutDistributionResult,
    E2EQualityMetrics,
)
from archium.domain.visual.enums import LayoutFamily
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository


class E2EBenchmarkService:
    """端到端 Benchmark 执行和评估服务"""

    def __init__(
        self,
        session: Session,
        benchmark_data_dir: Path,
    ) -> None:
        self._session = session
        self._data_dir = benchmark_data_dir
        self._presentations = PresentationRepository(session)
        self._ingestion = IngestionService(session)
        self._visual_edits = VisualEditService(session)
        self._validation = LayoutValidationService()
        self._deck_qa = DeckQAService()

    def run_case(self, case: E2EBenchmarkCase) -> E2EBenchmarkResult:
        """
        执行单个端到端案例。

        完整流程：
        1. 导入文档和素材（调用 IngestionService）
        2. 生成布局（调用 VisualEditService，让系统自主决策）
        3. 验证质量（调用 LayoutValidationService + DeckQAService）
        4. 检查是否符合期望标准
        """
        start_time = time.time()
        failure_reasons: list[str] = []

        try:
            # Step 1: 导入文档和素材
            document_paths = [self._data_dir / doc for doc in case.input_documents]
            image_paths = [self._data_dir / img for img in case.input_images]

            presentation = self._ingestion.import_from_files(
                task_description=case.task_description,
                document_paths=document_paths,
                image_paths=image_paths,
            )

            # Step 2: 为每个页面生成布局（系统自主决策）
            slides = self._presentations.list_slides(presentation.id)
            for slide in slides:
                try:
                    # 不预先指定任何参数，让 VisualEditService 自主决策：
                    # - LayoutFamily 选择
                    # - Variant 选择
                    # - 素材分配
                    self._visual_edits.regenerate_layout(slide.id)
                except WorkflowError as e:
                    failure_reasons.append(f"Slide {slide.order} 生成失败: {e}")

            # Step 3: 收集结果并评估
            slides = self._presentations.list_slides(presentation.id)
            plans = [self._presentations.get_layout_plan(slide.id) for slide in slides]
            plans = [p for p in plans if p is not None]

            # 验证每个页面
            validation_reports = []
            for plan in plans:
                report = self._validation.validate(
                    plan,
                    presentation.design_system,
                    require_source=False,
                )
                validation_reports.append(report)

            # DeckQA 评估
            deck_qa_report = self._deck_qa.evaluate(
                plans,
                slides=slides,
                design_system=presentation.design_system,
            )

            # Step 4: 对比期望标准
            expectations = case.expected_outcomes

            # 4.1 检查内容覆盖度
            content_result = None
            if expectations.content_expectations:
                content_result = self._check_content_coverage(
                    slides, expectations.content_expectations
                )
                if not content_result.passed:
                    failure_reasons.append("内容覆盖度不达标")

            # 4.2 检查 Hero Asset 使用
            hero_result = None
            if expectations.hero_asset_expectations:
                hero_result = self._check_hero_assets(
                    slides, plans, expectations.hero_asset_expectations, image_paths
                )
                if not hero_result.passed:
                    failure_reasons.append("Hero Asset 使用不当")

            # 4.3 检查布局分布
            layout_result = self._check_layout_distribution(
                plans, expectations.layout_distribution
            )
            if not layout_result.passed:
                failure_reasons.append("布局分布不符合预期")

            # 4.4 检查质量指标
            quality_metrics = self._compute_quality_metrics(
                slides, validation_reports, deck_qa_report, expectations
            )
            if not quality_metrics.passed:
                failure_reasons.append("质量指标不达标")

            # 判断总体通过状态
            passed = (
                len(failure_reasons) == 0
                and expectations.min_slide_count <= len(slides) <= expectations.max_slide_count
            )

            execution_time = time.time() - start_time

            return E2EBenchmarkResult(
                case_id=case.case_id,
                scenario=case.scenario,
                actual_slide_count=len(slides),
                execution_time_seconds=round(execution_time, 2),
                content_coverage=content_result,
                hero_asset_result=hero_result,
                layout_distribution=layout_result,
                quality_metrics=quality_metrics,
                passed=passed,
                failure_reasons=failure_reasons,
                slide_details=self._build_slide_details(slides, plans, validation_reports),
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return E2EBenchmarkResult(
                case_id=case.case_id,
                scenario=case.scenario,
                actual_slide_count=0,
                execution_time_seconds=round(execution_time, 2),
                quality_metrics=E2EQualityMetrics(
                    total_slides=0,
                    rule_passed_slides=0,
                    rule_pass_rate=0.0,
                    avg_layout_score=0.0,
                    deck_qa_score=0.0,
                    quality_score=0.0,
                    passed=False,
                ),
                passed=False,
                failure_reasons=[f"执行异常: {str(e)}"],
            )

    def run_suite(self, cases: list[E2EBenchmarkCase]) -> E2EBenchmarkSummary:
        """执行一组端到端案例并生成汇总报告"""
        results = [self.run_case(case) for case in cases]

        passed_cases = sum(1 for r in results if r.passed)
        failed_cases = len(results) - passed_cases

        # 按场景统计
        scenario_stats: dict[str, list[bool]] = {}
        for result in results:
            if result.scenario not in scenario_stats:
                scenario_stats[result.scenario] = []
            scenario_stats[result.scenario].append(result.passed)

        scenario_summary = {
            scenario: (len(passes), sum(passes))
            for scenario, passes in scenario_stats.items()
        }

        # 按难度统计
        difficulty_stats: dict[str, list[bool]] = {}
        for case, result in zip(cases, results):
            if case.difficulty not in difficulty_stats:
                difficulty_stats[case.difficulty] = []
            difficulty_stats[case.difficulty].append(result.passed)

        difficulty_summary = {
            difficulty: (len(passes), sum(passes))
            for difficulty, passes in difficulty_stats.items()
        }

        # 计算平均指标
        avg_execution_time = sum(r.execution_time_seconds for r in results) / len(results)
        avg_quality_score = sum(r.quality_metrics.quality_score for r in results) / len(results)
        avg_rule_pass_rate = sum(r.quality_metrics.rule_pass_rate for r in results) / len(results)
        avg_layout_score = sum(r.quality_metrics.avg_layout_score for r in results) / len(results)
        avg_deck_qa_score = sum(r.quality_metrics.deck_qa_score for r in results) / len(results)

        # 统计常见失败原因
        failure_counter: dict[str, int] = {}
        for result in results:
            for reason in result.failure_reasons:
                failure_counter[reason] = failure_counter.get(reason, 0) + 1

        common_failures = sorted(failure_counter.items(), key=lambda x: x[1], reverse=True)

        return E2EBenchmarkSummary(
            total_cases=len(results),
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            pass_rate=passed_cases / len(results) if results else 0.0,
            scenario_stats=scenario_summary,
            difficulty_stats=difficulty_summary,
            avg_execution_time=round(avg_execution_time, 2),
            avg_quality_score=round(avg_quality_score, 3),
            avg_rule_pass_rate=round(avg_rule_pass_rate, 3),
            avg_layout_score=round(avg_layout_score, 3),
            avg_deck_qa_score=round(avg_deck_qa_score, 3),
            common_failures=common_failures,
        )

    def _check_content_coverage(
        self, slides: list[Any], expectations: E2EContentExpectation
    ) -> E2EContentCoverageResult:
        """检查内容覆盖度"""
        # 收集所有文本
        all_text = " ".join([slide.title + " " + slide.message for slide in slides])
        all_text += " " + " ".join(
            [point for slide in slides for point in slide.key_points]
        )

        # 检查必需关键词
        required_found = [kw for kw in expectations.required_keywords if kw in all_text]
        required_missing = [kw for kw in expectations.required_keywords if kw not in all_text]

        # 检查禁止关键词
        forbidden_found = [kw for kw in expectations.forbidden_keywords if kw in all_text]

        # 检查标题长度
        title_violations = [
            (i, slide.title, len(slide.title))
            for i, slide in enumerate(slides)
            if not (expectations.min_title_length <= len(slide.title) <= expectations.max_title_length)
        ]

        # 检查要点数量
        key_points_violations = [
            (i, len(slide.key_points))
            for i, slide in enumerate(slides)
            if not (
                expectations.min_key_points_per_slide
                <= len(slide.key_points)
                <= expectations.max_key_points_per_slide
            )
        ]

        # 计算覆盖度得分
        required_score = len(required_found) / len(expectations.required_keywords) if expectations.required_keywords else 1.0
        forbidden_penalty = len(forbidden_found) * 0.2
        violation_penalty = (len(title_violations) + len(key_points_violations)) * 0.1

        coverage_score = max(0.0, required_score - forbidden_penalty - violation_penalty)

        passed = (
            len(required_missing) == 0
            and len(forbidden_found) == 0
            and len(title_violations) == 0
            and len(key_points_violations) == 0
        )

        return E2EContentCoverageResult(
            required_keywords_found=required_found,
            required_keywords_missing=required_missing,
            forbidden_keywords_found=forbidden_found,
            title_length_violations=title_violations,
            key_points_violations=key_points_violations,
            coverage_score=round(coverage_score, 3),
            passed=passed,
        )

    def _check_hero_assets(
        self,
        slides: list[Any],
        plans: list[Any],
        expectations: E2EHeroAssetExpectation,
        available_assets: list[Path],
    ) -> E2EHeroAssetResult:
        """检查 Hero Asset 使用情况"""
        # 收集使用的 hero assets
        hero_usage: dict[str, int] = {}
        for plan in plans:
            if plan.hero_element and plan.hero_element.asset_ref:
                asset_ref = plan.hero_element.asset_ref
                hero_usage[asset_ref] = hero_usage.get(asset_ref, 0) + 1

        total_hero_count = sum(hero_usage.values())
        unique_hero_count = len(hero_usage)
        max_reuse = max(hero_usage.values()) if hero_usage else 0

        # TODO: 检查素材标签（需要从 AssetMetadata 获取）
        preferred_tag_usage = 0
        avoided_tag_usage = 0

        # 计算使用率
        used_assets = set(hero_usage.keys())
        available_count = len(available_assets)
        usage_ratio = len(used_assets) / available_count if available_count > 0 else 0.0

        # 计算正确性得分
        correctness_score = 1.0
        if max_reuse > expectations.max_reuse_count:
            correctness_score -= 0.3
        if usage_ratio < expectations.min_usage_ratio:
            correctness_score -= 0.2
        correctness_score = max(0.0, correctness_score)

        passed = (
            max_reuse <= expectations.max_reuse_count
            and usage_ratio >= expectations.min_usage_ratio
        )

        unused = [str(p.name) for p in available_assets if str(p) not in used_assets]

        return E2EHeroAssetResult(
            total_hero_count=total_hero_count,
            unique_hero_count=unique_hero_count,
            preferred_tag_usage=preferred_tag_usage,
            avoided_tag_usage=avoided_tag_usage,
            max_reuse_count=max_reuse,
            unused_assets=unused,
            usage_ratio=round(usage_ratio, 3),
            correctness_score=round(correctness_score, 3),
            passed=passed,
        )

    def _check_layout_distribution(
        self, plans: list[Any], expectations: list[Any]
    ) -> E2ELayoutDistributionResult:
        """检查布局分布"""
        # 统计实际分布
        actual_dist: dict[LayoutFamily, int] = {}
        for plan in plans:
            family = plan.layout_family
            actual_dist[family] = actual_dist.get(family, 0) + 1

        # 检查每个期望
        violations = []
        for exp in expectations:
            actual_count = actual_dist.get(exp.layout_family, 0)
            if not exp.check(actual_count):
                violations.append(
                    (exp.layout_family, actual_count, exp.min_count, exp.max_count)
                )

        # 计算得分
        total_expectations = len(expectations)
        met_expectations = total_expectations - len(violations)
        distribution_score = met_expectations / total_expectations if total_expectations > 0 else 1.0

        passed = len(violations) == 0

        return E2ELayoutDistributionResult(
            actual_distribution=actual_dist,
            expected_distribution=expectations,
            violations=violations,
            distribution_score=round(distribution_score, 3),
            passed=passed,
        )

    def _compute_quality_metrics(
        self,
        slides: list[Any],
        validation_reports: list[Any],
        deck_qa_report: Any,
        expectations: Any,
    ) -> E2EQualityMetrics:
        """计算质量指标"""
        total_slides = len(slides)
        rule_passed = sum(1 for r in validation_reports if r.valid)
        rule_pass_rate = rule_passed / total_slides if total_slides > 0 else 0.0

        avg_layout_score = (
            sum(r.score for r in validation_reports) / len(validation_reports)
            if validation_reports
            else 0.0
        )

        deck_qa_score = deck_qa_report.total_score or 0.0

        # 综合质量得分（加权平均）
        quality_score = (
            rule_pass_rate * 0.4 + avg_layout_score * 0.3 + deck_qa_score * 0.3
        )

        # 判断是否通过
        passed = (
            rule_pass_rate >= expectations.min_rule_pass_rate
            and avg_layout_score >= expectations.min_avg_layout_score
            and deck_qa_score >= expectations.min_deck_qa_score
        )

        return E2EQualityMetrics(
            total_slides=total_slides,
            rule_passed_slides=rule_passed,
            rule_pass_rate=round(rule_pass_rate, 3),
            avg_layout_score=round(avg_layout_score, 3),
            deck_qa_score=round(deck_qa_score, 3),
            quality_score=round(quality_score, 3),
            passed=passed,
        )

    def _build_slide_details(
        self, slides: list[Any], plans: list[Any], reports: list[Any]
    ) -> list[dict[str, Any]]:
        """构建每页的详细信息"""
        details = []
        for slide, plan, report in zip(slides, plans, reports):
            details.append({
                "slide_order": slide.order,
                "title": slide.title,
                "layout_family": plan.layout_family.value if plan else None,
                "layout_variant": plan.variant if plan else None,
                "valid": report.valid,
                "score": round(report.score, 3),
                "issues": [
                    {"rule": issue.rule_code, "severity": issue.severity.value}
                    for issue in report.issues
                ],
            })
        return details
