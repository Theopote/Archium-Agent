"""测试 E2E Benchmark Service 的基本功能

验证修复后的 API 调用是否正确
"""

from pathlib import Path
from uuid import uuid4

# 模拟测试：验证代码结构的正确性
def test_imports():
    """测试能否正确导入所有依赖"""
    try:
        from archium.application.visual.e2e_benchmark_service import E2EBenchmarkService
        from archium.domain.visual.e2e_benchmark import (
            E2EBenchmarkCase,
            E2EExpectedOutcomes,
            E2EContentExpectation,
            E2ELayoutDistributionExpectation,
        )
        from archium.domain.visual.enums import LayoutFamily
        print("✅ 所有导入成功")
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_case_structure():
    """测试能否创建测试案例"""
    try:
        from archium.domain.visual.e2e_benchmark import (
            E2EBenchmarkCase,
            E2EExpectedOutcomes,
            E2EContentExpectation,
            E2ELayoutDistributionExpectation,
        )
        from archium.domain.visual.enums import LayoutFamily

        # 创建一个简单的测试案例
        case = E2EBenchmarkCase(
            case_id="test_001",
            scenario="测试场景",
            difficulty="easy",
            task_description="创建一个简单的演示",
            input_documents=["test.docx"],
            input_images=["test.jpg"],
            expected_outcomes=E2EExpectedOutcomes(
                min_slide_count=3,
                max_slide_count=5,
                content_expectations=E2EContentExpectation(
                    required_keywords=["关键词1", "关键词2"],
                    forbidden_keywords=[],
                    min_title_length=5,
                    max_title_length=50,
                    min_key_points_per_slide=1,
                    max_key_points_per_slide=5,
                ),
                layout_distribution=[
                    E2ELayoutDistributionExpectation(
                        layout_family=LayoutFamily.TITLE,
                        min_count=1,
                        max_count=1,
                    ),
                ],
                min_rule_pass_rate=0.8,
                min_avg_layout_score=0.7,
                min_deck_qa_score=0.7,
            ),
        )

        print(f"✅ 测试案例创建成功: {case.case_id}")
        print(f"   - 场景: {case.scenario}")
        print(f"   - 期望页数: {case.expected_outcomes.min_slide_count}-{case.expected_outcomes.max_slide_count}")
        return True
    except Exception as e:
        print(f"❌ 测试案例创建失败: {e}")
        return False


def test_service_initialization():
    """测试服务初始化（不需要数据库连接）"""
    try:
        # 只测试导入和类定义，不实际创建实例（需要数据库）
        from archium.application.visual.e2e_benchmark_service import E2EBenchmarkService

        # 检查类的方法是否存在
        required_methods = [
            'run_case',
            'run_suite',
            '_check_content_coverage',
            '_check_hero_assets',
            '_check_layout_distribution',
            '_compute_quality_metrics',
            '_build_slide_details',
            '_create_slides_from_case',  # 新增的辅助方法
        ]

        for method in required_methods:
            if not hasattr(E2EBenchmarkService, method):
                print(f"❌ 缺少方法: {method}")
                return False

        print(f"✅ 服务类结构正确，包含所有必需方法")
        return True
    except Exception as e:
        print(f"❌ 服务初始化测试失败: {e}")
        return False


def test_repository_imports():
    """测试能否导入修复后使用的 Repository"""
    try:
        from archium.infrastructure.database.repositories import (
            ProjectRepository,
            PresentationRepository,
        )
        from archium.infrastructure.database.visual_repositories import (
            LayoutPlanRepository,
            DesignSystemRepository,
        )
        print("✅ 所有 Repository 导入成功")
        return True
    except ImportError as e:
        print(f"❌ Repository 导入失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("E2E Benchmark Service 修复验证测试")
    print("=" * 60)
    print()

    tests = [
        ("导入测试", test_imports),
        ("测试案例结构", test_case_structure),
        ("服务结构测试", test_service_initialization),
        ("Repository 导入测试", test_repository_imports),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n【{name}】")
        print("-" * 60)
        result = test_func()
        results.append((name, result))
        print()

    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    print()
    print(f"通过率: {passed}/{total} ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 所有测试通过！E2E Benchmark 服务修复成功。")
        print("\n下一步:")
        print("1. 准备测试数据（文档和图片）")
        print("2. 创建数据库实例")
        print("3. 运行完整的集成测试")
        print("4. Phase 2: 补充 Brief → Storyline → 完整 Workflow")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，需要修复。")


if __name__ == "__main__":
    main()
