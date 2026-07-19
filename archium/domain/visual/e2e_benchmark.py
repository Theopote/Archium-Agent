"""End-to-End Benchmark domain models and service.

验证完整的产品能力：从原始输入到最终输出。
不预先指定 LayoutFamily、素材、Variant，让系统自主决策。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from pydantic import Field


class E2EBenchmarkScenario(str):
    """端到端 Benchmark 的典型场景类型"""

    PRODUCT_INTRO = "product_intro"  # 产品介绍（图文并茂）
    DATA_REPORT = "data_report"  # 数据报告（图表密集）
    PROJECT_PROPOSAL = "project_proposal"  # 项目提案（结构化文本）
    ACADEMIC_TALK = "academic_talk"  # 学术演讲（概念图示）
    EVENT_PROMOTION = "event_promotion"  # 活动宣传（视觉驱动）


@dataclass(frozen=True)
class E2EInputDocument:
    """端到端案例的输入文档"""

    path: Path
    document_type: str  # "pdf" | "docx" | "pptx" | "txt"
    description: str  # 文档内容描述


@dataclass(frozen=True)
class E2EInputAsset:
    """端到端案例的输入素材"""

    path: Path
    asset_type: str  # "image" | "chart" | "diagram" | "photo"
    description: str  # 素材内容描述
    tags: list[str] = field(default_factory=list)  # 语义标签


@dataclass(frozen=True)
class E2ELayoutDistributionExpectation:
    """期望的布局族分布"""

    layout_family: LayoutFamily
    min_count: int  # 至少应出现的次数
    max_count: int  # 最多应出现的次数

    def check(self, actual_count: int) -> bool:
        """检查实际数量是否在期望范围内"""
        return self.min_count <= actual_count <= self.max_count


@dataclass(frozen=True)
class E2EHeroAssetExpectation:
    """Hero Asset 选择的期望标准"""

    should_prefer_tags: list[str] = field(default_factory=list)  # 应优先选择的标签
    should_avoid_tags: list[str] = field(default_factory=list)  # 应避免的标签
    min_usage_ratio: float = 0.0  # 至少应被使用的比例（0.0-1.0）
    max_reuse_count: int = 999  # 单个素材最多重复使用次数


@dataclass(frozen=True)
class E2EContentExpectation:
    """内容提取的期望标准"""

    required_keywords: list[str] = field(default_factory=list)  # 必须出现的关键词
    forbidden_keywords: list[str] = field(default_factory=list)  # 不应出现的关键词
    min_title_length: int = 3  # 标题最短长度
    max_title_length: int = 50  # 标题最长长度
    min_key_points_per_slide: int = 0  # 每页至少要点数
    max_key_points_per_slide: int = 7  # 每页最多要点数


class E2EExpectedOutcomes(DomainModel):
    """端到端案例的期望输出质量标准"""

    min_slide_count: int = Field(ge=1)
    max_slide_count: int = Field(ge=1)

    # 内容质量
    content_expectations: E2EContentExpectation | None = None

    # 素材使用
    hero_asset_expectations: E2EHeroAssetExpectation | None = None

    # 布局分布
    layout_distribution: list[E2ELayoutDistributionExpectation] = Field(default_factory=list)

    # 质量阈值
    min_rule_pass_rate: float = Field(ge=0.0, le=1.0, default=0.9)  # 至少 90% 页面通过规则
    min_avg_layout_score: float = Field(ge=0.0, le=1.0, default=0.8)  # 平均布局得分
    min_deck_qa_score: float = Field(ge=0.0, le=1.0, default=0.75)  # DeckQA 得分

    # 容错设置
    allow_partial_success: bool = True  # 允许部分成功（如某些页面失败）
    max_failed_slides: int = 2  # 最多允许失败的页面数


class E2EBenchmarkCase(DomainModel):
    """端到端基准案例定义"""

    case_id: str = Field(min_length=1)
    scenario: str  # E2EBenchmarkScenario
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)

    # 用户任务描述（模拟真实用户输入）
    task_description: str = Field(min_length=1)

    # 输入文件路径（相对于 benchmark data 目录）
    input_documents: list[str] = Field(default_factory=list)
    input_images: list[str] = Field(default_factory=list)

    # 期望的输出质量
    expected_outcomes: E2EExpectedOutcomes

    # 元数据
    difficulty: str = "medium"  # "easy" | "medium" | "hard"
    tags: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class E2EContentCoverageResult:
    """内容覆盖度检查结果"""

    required_keywords_found: list[str]
    required_keywords_missing: list[str]
    forbidden_keywords_found: list[str]
    title_length_violations: list[tuple[int, str, int]]  # (slide_idx, title, length)
    key_points_violations: list[tuple[int, int]]  # (slide_idx, count)
    coverage_score: float  # 0.0-1.0
    passed: bool


@dataclass(frozen=True)
class E2EHeroAssetResult:
    """Hero Asset 使用检查结果"""

    total_hero_count: int  # 使用了 hero 的页面数
    unique_hero_count: int  # 唯一 hero 数量
    preferred_tag_usage: int  # 使用了优选标签的次数
    avoided_tag_usage: int  # 使用了应避免标签的次数
    max_reuse_count: int  # 单个素材的最大重用次数
    unused_assets: list[str]  # 未使用的素材
    usage_ratio: float  # 素材使用率
    correctness_score: float  # 0.0-1.0
    passed: bool


@dataclass(frozen=True)
class E2ELayoutDistributionResult:
    """布局分布检查结果"""

    actual_distribution: dict[LayoutFamily, int]
    expected_distribution: list[E2ELayoutDistributionExpectation]
    violations: list[tuple[LayoutFamily, int, int, int]]  # (family, actual, min, max)
    distribution_score: float  # 0.0-1.0
    passed: bool


@dataclass(frozen=True)
class E2EQualityMetrics:
    """端到端质量指标"""

    total_slides: int
    rule_passed_slides: int
    rule_pass_rate: float
    avg_layout_score: float
    deck_qa_score: float
    quality_score: float  # 综合质量得分
    passed: bool


class E2EBenchmarkResult(DomainModel):
    """端到端基准案例的评估结果"""

    case_id: str
    scenario: str

    # 基本统计
    actual_slide_count: int
    execution_time_seconds: float

    # 分项检查结果
    content_coverage: E2EContentCoverageResult | None = None
    hero_asset_result: E2EHeroAssetResult | None = None
    layout_distribution: E2ELayoutDistributionResult | None = None
    quality_metrics: E2EQualityMetrics

    # 总体通过状态
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)

    # 详细信息
    slide_details: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class E2EBenchmarkSummary:
    """多个端到端案例的汇总统计"""

    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float

    # 按场景统计
    scenario_stats: dict[str, tuple[int, int]]  # scenario -> (total, passed)

    # 按难度统计
    difficulty_stats: dict[str, tuple[int, int]]  # difficulty -> (total, passed)

    # 平均指标
    avg_execution_time: float
    avg_quality_score: float
    avg_rule_pass_rate: float
    avg_layout_score: float
    avg_deck_qa_score: float

    # 常见失败原因
    common_failures: list[tuple[str, int]]  # (reason, count)


# 默认期望标准（可在具体案例中覆盖）
DEFAULT_E2E_OUTCOMES = E2EExpectedOutcomes(
    min_slide_count=3,
    max_slide_count=15,
    min_rule_pass_rate=0.85,
    min_avg_layout_score=0.75,
    min_deck_qa_score=0.70,
    allow_partial_success=True,
    max_failed_slides=2,
)
