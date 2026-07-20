"""End-to-End Benchmark Service.

执行完整的端到端验证：
1. 模拟用户导入文档和素材
2. 让系统自主完成布局相关决策（不预先指定 LayoutFamily/Variant）
3. 评估最终输出质量
4. 对比期望标准

注意：当前支持四种执行模式：
- ``lite``：SlideSpec 由 case 预置（默认）
- ``content``：Brief → Storyline → SlideSpec（需 ``enable_content_planning`` + LLM）
- ``full``：content/lite 页面 + VisualWorkflowService（需 ``enable_visual_workflow``）
- ``deliverable``：full + PPTX 导出 + screenshot 检查（需 ``enable_pptx_export``）

Nightly 质量门禁（M5）：``tests/integration/visual/test_e2e_quality_gate.py``（``@pytest.mark.e2e``），
要求 ``passed=True``；见 ``.github/workflows/e2e-benchmark-nightly.yml``。

仍未实现：Screenshot QA 视觉回归基线对比。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.ingestion_service import IngestionService
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_service import PresentationService
from archium.application.project_acceptance_service import (
    _attach_project_assets,
)
from archium.application.visual.deck_qa_service import DeckQAService
from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.slide_preview_service import map_preview_pngs_by_order
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.application.visual.visual_workflow_service import (
    VisualWorkflowResult,
    VisualWorkflowService,
)
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.e2e_benchmark import (
    E2EBenchmarkCase,
    E2EBenchmarkResult,
    E2EBenchmarkSummary,
    E2EContentCoverageResult,
    E2EContentExpectation,
    E2EDeliverableResult,
    E2EExecutionMode,
    E2EHeroAssetExpectation,
    E2EHeroAssetResult,
    E2ELayoutDistributionResult,
    E2EQualityMetrics,
)
from archium.domain.visual.enums import LayoutFamily
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    AssetRepository,
    PresentationRepository,
    ProjectRepository,
)
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.pptx_screenshot import screenshot_tools_available

E2E_LITE_NOTES = (
    "E2E Lite: SlideSpec 由 case 预置；未执行 Brief/Storyline/Visual Workflow/"
    "PPTX/Screenshot；Hero 选图能力仅验证已导入素材是否被引用。"
)
E2E_CONTENT_NOTES = (
    "E2E Content: 已通过 Brief → Storyline → SlideSpec 从导入资料生成页面；"
    "仍未执行 Visual Workflow / PPTX / Screenshot。"
)
E2E_FULL_NOTES = (
    "E2E Full: 已执行 VisualWorkflowService（ArtDirection → Composition → "
    "Layout → Render）；未导出 PPTX / Screenshot。"
)
E2E_DELIVERABLE_NOTES = (
    "E2E Deliverable: Visual Workflow + PPTX 导出 + slide screenshot 检查；"
    "LibreOffice/pdftoppm 不可用时 screenshot 检查 soft-skip。"
)
E2E_LITE_SKIPPED = [
    "brief_generation",
    "storyline_generation",
    "slidespec_auto_generation",
    "visual_workflow",
    "pptx_export",
    "screenshot_qa",
    "autonomous_hero_selection_from_unlabeled_pool",
]


class E2EBenchmarkService:
    """端到端 Benchmark 执行和评估服务。"""

    def __init__(
        self,
        session: Session,
        benchmark_data_dir: Path,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._data_dir = benchmark_data_dir
        self._llm = llm
        self._settings = settings or get_settings()
        self._projects = ProjectRepository(session)
        self._presentations = PresentationRepository(session)
        self._ingestion = IngestionService(session)
        self._intent_service = VisualIntentService(session)
        self._layout_planning = LayoutPlanningService(session)
        self._validation = LayoutValidationService()
        self._deck_qa = DeckQAService()
        self._layout_plans = LayoutPlanRepository(session)
        self._design_systems = DesignSystemRepository(session)
        self._art_directions = ArtDirectionRepository(session)
        self._visual_intents = VisualIntentRepository(session)
        self._assets = AssetRepository(session)

    def run_case(self, case: E2EBenchmarkCase) -> E2EBenchmarkResult:
        """执行单个 E2E 案例（lite / content / full / deliverable）。"""
        start_time = time.time()
        failure_reasons: list[str] = []
        design_system: DesignSystem | None = None
        imported_assets: list[Asset] = []

        if case.enable_pptx_export and not case.enable_visual_workflow:
            failure_reasons.append("enable_pptx_export 需要 enable_visual_workflow")
        if case.enable_screenshot_check and not case.enable_pptx_export:
            failure_reasons.append("enable_screenshot_check 需要 enable_pptx_export")

        try:
            project = Project(
                id=uuid4(),
                name=f"E2E_Benchmark_{case.case_id}",
                description=case.task_description,
            )
            project = self._projects.create(project)

            design_system, art_direction = self._create_case_design_binding(
                project_id=project.id,
                case=case,
            )

            document_paths = [self._data_dir / doc for doc in case.input_documents]
            image_paths = [self._data_dir / img for img in case.input_images]

            for doc_path in document_paths:
                if not doc_path.exists():
                    failure_reasons.append(f"文档不存在: {doc_path}")
                    continue
                result = self._ingestion.import_file(project.id, doc_path)
                if result.error:
                    failure_reasons.append(f"导入文档失败 {doc_path.name}: {result.error}")

            for image_path in image_paths:
                if not image_path.exists():
                    failure_reasons.append(f"图片不存在: {image_path}")
                    continue
                result = self._ingestion.import_file(project.id, image_path)
                if result.error:
                    failure_reasons.append(f"导入图片失败 {image_path.name}: {result.error}")
                else:
                    imported_assets.extend(result.assets)

            presentation: Presentation | None = None
            slides: list[SlideSpec] = []
            execution_mode: E2EExecutionMode = "lite"

            if case.enable_content_planning and self._llm is not None:
                try:
                    presentation, slides = self._plan_slides_from_imported_content(
                        project.id,
                        case,
                    )
                    execution_mode = "content"
                except Exception as e:
                    failure_reasons.append(f"内容规划失败: {e}")

            if presentation is None:
                presentation = self._presentations.create_presentation(
                    Presentation(
                        id=uuid4(),
                        project_id=project.id,
                        title=case.title,
                    )
                )

            if not slides:
                slides = self._create_slides_from_case(case, presentation.id)
                for slide in slides:
                    self._presentations.save_slide(slide)

            visual_layout_plan_count = 0
            visual_result: VisualWorkflowResult | None = None
            if case.enable_visual_workflow:
                if not case.enable_content_planning:
                    art_direction.presentation_id = presentation.id
                    self._art_directions.save(art_direction)
                execution_mode = "full"
                try:
                    visual_result = self._run_visual_workflow_for_case(
                        project_id=project.id,
                        presentation_id=presentation.id,
                        design_system_id=design_system.id,
                        imported_assets=imported_assets,
                        export_pptx=case.enable_pptx_export,
                        failure_reasons=failure_reasons,
                    )
                    visual_layout_plan_count = len(visual_result.layout_plan_ids)
                except Exception as e:
                    failure_reasons.append(f"Visual Workflow 失败: {e}")
            else:
                art_direction.presentation_id = presentation.id
                self._art_directions.save(art_direction)
                for slide in slides:
                    try:
                        self._generate_layout_for_slide(
                            slide=slide,
                            art_direction_id=art_direction.id,
                            design_system_id=design_system.id,
                        )
                    except (WorkflowError, ValueError) as e:
                        failure_reasons.append(f"Slide {slide.order} 生成失败: {e}")

            slides = self._presentations.list_slides(presentation.id)

            plans = []
            for slide in slides:
                if slide.layout_plan_id:
                    plan = self._layout_plans.get(slide.layout_plan_id)
                    if plan:
                        plans.append(plan)

            validation_reports = []
            for plan in plans:
                report = self._validation.validate(
                    plan,
                    design_system,
                    require_source=False,
                )
                validation_reports.append(report)

            deck_qa_report = None
            if plans:
                deck_qa_report = self._deck_qa.evaluate(
                    plans,
                    slides=slides,
                    design_system=design_system,
                )

            expectations = case.expected_outcomes

            content_result = None
            if expectations.content_expectations:
                content_result = self._check_content_coverage(
                    slides, expectations.content_expectations
                )
                if not content_result.passed:
                    failure_reasons.append("内容覆盖度不达标")

            hero_result = None
            if expectations.hero_asset_expectations:
                hero_result = self._check_hero_assets(
                    plans,
                    expectations.hero_asset_expectations,
                    imported_assets,
                )
                if not hero_result.passed:
                    failure_reasons.append("Hero Asset 使用不当")

            layout_result = self._check_layout_distribution(
                plans, expectations.layout_distribution
            )
            if not layout_result.passed:
                failure_reasons.append("布局分布不符合预期")

            quality_metrics = self._compute_quality_metrics(
                slides, validation_reports, deck_qa_report, expectations
            )
            if not quality_metrics.passed:
                failure_reasons.append("质量指标不达标")

            deliverable_result = None
            if case.enable_pptx_export or case.enable_screenshot_check:
                deliverable_result = self._evaluate_deliverables(
                    case=case,
                    visual_result=visual_result,
                    slide_count=len(slides),
                )
                if case.enable_pptx_export and not deliverable_result.pptx_exported:
                    failure_reasons.append("PPTX 未导出")
                if (
                    case.enable_screenshot_check
                    and deliverable_result.screenshot_tools_available
                    and deliverable_result.screenshot_count < len(slides)
                ):
                    failure_reasons.append(
                        "Screenshot 数量不足: "
                        f"{deliverable_result.screenshot_count}/{len(slides)}"
                    )

            passed = (
                len(failure_reasons) == 0
                and expectations.min_slide_count <= len(slides) <= expectations.max_slide_count
            )

            execution_time = time.time() - start_time

            return E2EBenchmarkResult(
                case_id=case.case_id,
                scenario=case.scenario,
                execution_mode=execution_mode,
                design_system_id=design_system.id,
                imported_asset_count=len(imported_assets),
                visual_layout_plan_count=visual_layout_plan_count,
                deliverable=deliverable_result,
                actual_slide_count=len(slides),
                execution_time_seconds=round(execution_time, 2),
                content_coverage=content_result,
                hero_asset_result=hero_result,
                layout_distribution=layout_result,
                quality_metrics=quality_metrics,
                passed=passed,
                failure_reasons=failure_reasons,
                slide_details=self._build_slide_details(slides, plans, validation_reports),
                notes=self._notes_for_mode(
                    execution_mode,
                    enable_deliverables=case.enable_pptx_export,
                ),
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return E2EBenchmarkResult(
                case_id=case.case_id,
                scenario=case.scenario,
                execution_mode="lite",
                design_system_id=design_system.id if design_system else None,
                imported_asset_count=len(imported_assets),
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
                notes=E2E_LITE_NOTES,
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
        for case, result in zip(cases, results, strict=False):
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
        plans: list[Any],
        expectations: E2EHeroAssetExpectation,
        imported_assets: list[Asset],
    ) -> E2EHeroAssetResult:
        """检查 Hero Asset 是否引用已导入素材（Lite：不验证自主选图逻辑）。"""
        hero_usage: dict[str, int] = {}
        for plan in plans:
            hero = (
                plan.element_by_id(plan.hero_element_id)
                if plan.hero_element_id
                else None
            )
            if hero is None or not hero.content_ref:
                continue
            asset_ref = hero.content_ref
            hero_usage[asset_ref] = hero_usage.get(asset_ref, 0) + 1

        total_hero_count = sum(hero_usage.values())
        unique_hero_count = len(hero_usage)
        max_reuse = max(hero_usage.values()) if hero_usage else 0

        preferred_tag_usage = 0
        avoided_tag_usage = 0

        imported_refs = {
            str(asset.id): asset
            for asset in imported_assets
        }
        imported_refs.update(
            {asset.path: asset for asset in imported_assets}
        )
        imported_refs.update(
            {asset.filename: asset for asset in imported_assets}
        )

        used_assets = set(hero_usage.keys())
        available_count = len(imported_assets)
        matched_used = {
            ref
            for ref in used_assets
            if ref in imported_refs or any(ref in key for key in imported_refs)
        }
        usage_ratio = len(matched_used) / available_count if available_count > 0 else 1.0

        correctness_score = 1.0
        if max_reuse > expectations.max_reuse_count:
            correctness_score -= 0.3
        if available_count > 0 and usage_ratio < expectations.min_usage_ratio:
            correctness_score -= 0.2
        correctness_score = max(0.0, correctness_score)

        passed = (
            max_reuse <= expectations.max_reuse_count
            and (available_count == 0 or usage_ratio >= expectations.min_usage_ratio)
        )

        unused = [
            asset.filename
            for asset in imported_assets
            if asset.filename not in used_assets
            and str(asset.id) not in used_assets
            and asset.path not in used_assets
        ]

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

        deck_qa_score = deck_qa_report.total_score if deck_qa_report else 0.0

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
        for slide, plan, report in zip(slides, plans, reports, strict=False):
            details.append({
                "slide_order": slide.order,
                "title": slide.title,
                "layout_family": plan.layout_family.value if plan else None,
                "layout_variant": plan.layout_variant if plan else None,
                "valid": report.valid,
                "score": round(report.score, 3),
                "issues": [
                    {"rule": issue.rule_code, "severity": issue.severity.value}
                    for issue in report.issues
                ],
            })
        return details

    def _create_slides_from_case(
        self, case: E2EBenchmarkCase, presentation_id: UUID
    ) -> list[SlideSpec]:
        """从测试案例手动构建 SlideSpec

        注意：这是简化版本的临时实现
        完整实现应该：
        1. 从导入的文档中提取内容
        2. 通过 Brief → Storyline 生成逻辑结构
        3. 自动生成 SlideSpec

        当前实现：
        - 从 case.expected_outcomes.content_expectations 提取内容
        - 手动构建最小化的 SlideSpec
        - 仅用于测试布局生成能力
        """
        slides: list[SlideSpec] = []

        # 如果 case 有明确的内容期望，尝试从中构建 slides
        content_exp = case.expected_outcomes.content_expectations
        if content_exp and content_exp.required_keywords:
            # 创建一个包含必需关键词的标题页
            slide = SlideSpec(
                id=uuid4(),
                presentation_id=presentation_id,
                chapter_id="benchmark",
                order=0,
                title=case.task_description[:50],
                message=" ".join(content_exp.required_keywords[:3]),
                key_points=content_exp.required_keywords[:5],
                slide_type=SlideType.CONTENT,
            )
            slides.append(slide)
        else:
            # 默认创建一个简单的标题页
            slide = SlideSpec(
                id=uuid4(),
                presentation_id=presentation_id,
                chapter_id="benchmark",
                order=0,
                title=case.task_description[:50],
                message="自动生成的测试页面",
                key_points=["测试要点1", "测试要点2", "测试要点3"],
                slide_type=SlideType.CONTENT,
            )
            slides.append(slide)

        # 根据期望的 slide 数量创建更多页面
        expected_count = case.expected_outcomes.min_slide_count
        for i in range(1, expected_count):
            slide = SlideSpec(
                id=uuid4(),
                presentation_id=presentation_id,
                chapter_id="benchmark",
                order=i,
                title=f"页面 {i + 1}",
                message=f"这是第 {i + 1} 页的内容",
                key_points=[f"要点 {i + 1}.1", f"要点 {i + 1}.2", f"要点 {i + 1}.3"],
                slide_type=SlideType.CONTENT,
            )
            slides.append(slide)

        return slides

    def _create_case_design_binding(
        self,
        *,
        project_id: UUID,
        case: E2EBenchmarkCase,
    ) -> tuple[DesignSystem, ArtDirection]:
        """Create an isolated DesignSystem + ArtDirection for one benchmark case."""
        design = default_presentation_design_system()
        design.name = f"E2E Benchmark · {case.case_id}"
        design = self._design_systems.save(design)

        art_direction = ArtDirection(
            id=uuid4(),
            project_id=project_id,
            concept_name=f"E2E Benchmark {case.case_id}",
            rationale=case.description,
            visual_tone=["professional"],
            palette_strategy="neutral",
            typography_strategy="default",
            grid_strategy="12-col",
            image_strategy="contain",
            drawing_strategy="dominant",
            diagram_strategy="minimal",
            annotation_strategy="caption",
            cover_strategy="hero",
            section_strategy="title",
            content_strategy="balanced",
            closing_strategy="summary",
            pacing_strategy="steady",
            design_system_id=design.id,
            approval_status=ApprovalStatus.APPROVED,
        )
        art_direction = self._art_directions.save(art_direction)
        return design, art_direction

    def _generate_layout_for_slide(
        self,
        *,
        slide: SlideSpec,
        art_direction_id: UUID,
        design_system_id: UUID,
    ) -> None:
        """Generate VisualIntent + LayoutPlan for one slide (Lite path)."""
        intent = self._intent_service.generate_for_slide(slide, use_llm=False)
        intent = self._visual_intents.save(intent)
        slide.visual_intent_id = intent.id

        plan = self._layout_planning.plan_slide(
            slide=slide,
            visual_intent_id=intent.id,
            art_direction_id=art_direction_id,
            design_system_id=design_system_id,
            candidate_count=1,
        )
        slide.layout_plan_id = plan.id
        self._presentations.save_slide(slide)

    def _build_presentation_request(self, case: E2EBenchmarkCase) -> PresentationRequest:
        expectations = case.expected_outcomes
        required_sections: list[str] = []
        if expectations.content_expectations:
            required_sections = list(expectations.content_expectations.required_keywords)
        return PresentationRequest(
            title=case.title,
            audience="项目相关方",
            purpose=case.task_description,
            duration_minutes=20,
            target_slide_count=expectations.max_slide_count,
            core_message=case.task_description,
            required_sections=required_sections,
            user_notes=case.description,
        )

    def _plan_slides_from_imported_content(
        self,
        project_id: UUID,
        case: E2EBenchmarkCase,
    ) -> tuple[Presentation, list[SlideSpec]]:
        """Brief → Storyline → SlideSpec via PresentationService."""
        if self._llm is None:
            raise WorkflowError("内容规划需要 LLM provider")

        request = self._build_presentation_request(case)
        presentation_service = PresentationService(
            self._session,
            self._llm,
            settings=self._settings,
        )
        presentation = presentation_service.create_presentation(project_id, request)
        brief = presentation_service.generate_brief(project_id, presentation.id, request)
        storyline = presentation_service.generate_storyline(project_id, brief)
        slides = presentation_service.generate_slide_plan(project_id, brief, storyline)
        if not slides:
            raise WorkflowError("内容规划未生成任何 SlideSpec")
        return presentation, slides

    def _run_visual_workflow_for_case(
        self,
        *,
        project_id: UUID,
        presentation_id: UUID,
        design_system_id: UUID,
        imported_assets: list[Asset],
        export_pptx: bool,
        failure_reasons: list[str],
    ) -> VisualWorkflowResult:
        assets = imported_assets or self._assets.list_by_project(project_id)
        _attach_project_assets(
            self._presentations,
            presentation_id,
            project_id,
            assets,
        )

        visual_service = VisualWorkflowService(
            self._session,
            llm=self._llm,
            settings=self._settings,
        )
        try:
            result = visual_service.run(
                project_id,
                presentation_id,
                require_art_direction_review=False,
                use_llm=False,
                export_pptx=export_pptx,
                export_layout_instructions=True,
                candidate_count=1,
                max_repair_rounds=1,
                design_system_id=design_system_id,
            )
            result = self._resume_visual_if_paused(visual_service, result)
            if not result.succeeded:
                failure_reasons.append("Visual Workflow 未完成")
                failure_reasons.extend(result.errors)
            return result
        finally:
            visual_service.close()

    def _evaluate_deliverables(
        self,
        *,
        case: E2EBenchmarkCase,
        visual_result: VisualWorkflowResult | None,
        slide_count: int,
    ) -> E2EDeliverableResult:
        render_paths = list(visual_result.render_paths) if visual_result else []
        pptx_paths = [path for path in render_paths if path.lower().endswith(".pptx")]
        pptx_exported = bool(pptx_paths)
        pptx_path = pptx_paths[0] if pptx_paths else None

        tools_available = screenshot_tools_available()
        preview_by_order = map_preview_pngs_by_order(render_paths)
        screenshot_paths = list(preview_by_order.values())
        screenshot_count = len(screenshot_paths)

        passed = True
        if case.enable_pptx_export and not pptx_exported:
            passed = False
        if case.enable_screenshot_check and tools_available and screenshot_count < slide_count:
            passed = False

        return E2EDeliverableResult(
            pptx_exported=pptx_exported,
            pptx_path=pptx_path,
            screenshot_count=screenshot_count,
            screenshot_paths=screenshot_paths,
            screenshot_tools_available=tools_available,
            passed=passed,
        )

    @staticmethod
    def _resume_visual_if_paused(
        visual_service: VisualWorkflowService,
        result: VisualWorkflowResult,
    ) -> VisualWorkflowResult:
        if result.succeeded or not result.awaiting_review:
            return result
        gate = result.review_gate
        if gate == "layout_review":
            return visual_service.continue_after_layout_review(
                result.workflow_run.id,
                allow_invalid_layout_export=True,
            )
        if gate == "art_direction":
            return visual_service.continue_after_art_direction_approval(result.workflow_run.id)
        return result

    @staticmethod
    def _notes_for_mode(
        mode: E2EExecutionMode,
        *,
        enable_deliverables: bool = False,
    ) -> str:
        if enable_deliverables:
            return E2E_DELIVERABLE_NOTES
        if mode == "full":
            return E2E_FULL_NOTES
        if mode == "content":
            return E2E_CONTENT_NOTES
        return E2E_LITE_NOTES

