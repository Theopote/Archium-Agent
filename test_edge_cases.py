"""测试边界案例的 Benchmark 执行

验证边界案例能否正常通过规则验证：
- edge_031: 极少内容（仅标题）
- edge_032: 极多内容（10+ 要点）
- edge_033: 无素材（纯文字）
- edge_034: 冲突素材（横竖混合）
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tests.benchmark.architectural_slides.case_catalog import get_catalog_entry
from archium.application.visual.benchmark_service import (
    BenchmarkService,
    BenchmarkCaseBuildRequest,
    BenchmarkSlideContent,
)
from archium.domain.visual.design_system import DesignSystem
from archium.infrastructure.database.repositories import DesignSystemRepository


def test_edge_cases():
    """测试 4 个边界案例"""

    edge_cases = [
        "edge_031_minimal_content",
        "edge_032_excessive_content",
        "edge_033_no_assets",
        "edge_034_conflicting_assets",
    ]

    print("=" * 80)
    print("边界案例 Benchmark 测试")
    print("=" * 80)

    # 使用内存服务（不需要数据库）
    service = BenchmarkService()

    # 创建默认设计系统
    design_system = DesignSystem.model_validate({
        "name": "Test Design System",
        "page": {
            "width": 10.0,
            "height": 7.5,
            "margin_top": 0.5,
            "margin_right": 0.5,
            "margin_bottom": 0.5,
            "margin_left": 0.5,
        },
        "grid": {
            "grid_type": "column",
            "columns": 12,
            "gutter": 0.15,
        },
        "spacing": {
            "xs": 0.05,
            "sm": 0.10,
            "md": 0.20,
            "lg": 0.30,
            "xl": 0.40,
            "xxl": 0.60,
        },
        "typography": {
            "display": {
                "font_family": "思源黑体",
                "font_size": 48,
                "font_weight": 700,
                "line_height": 56,
                "color_token": "primary",
            },
            "title": {
                "font_family": "思源黑体",
                "font_size": 32,
                "font_weight": 600,
                "line_height": 40,
                "color_token": "primary",
            },
            "subtitle": {
                "font_family": "思源黑体",
                "font_size": 24,
                "font_weight": 500,
                "line_height": 32,
                "color_token": "secondary",
            },
            "heading": {
                "font_family": "思源黑体",
                "font_size": 20,
                "font_weight": 600,
                "line_height": 28,
                "color_token": "primary",
            },
            "body": {
                "font_family": "思源黑体",
                "font_size": 16,
                "font_weight": 400,
                "line_height": 24,
                "color_token": "body",
            },
            "caption": {
                "font_family": "思源黑体",
                "font_size": 12,
                "font_weight": 400,
                "line_height": 18,
                "color_token": "secondary",
            },
            "metric": {
                "font_family": "思源黑体",
                "font_size": 36,
                "font_weight": 700,
                "line_height": 44,
                "color_token": "accent",
            },
            "footnote": {
                "font_family": "思源黑体",
                "font_size": 10,
                "font_weight": 400,
                "line_height": 14,
                "color_token": "tertiary",
            },
        },
        "colors": {
            "primary": "#1a1a1a",
            "secondary": "#666666",
            "tertiary": "#999999",
            "accent": "#0066cc",
            "body": "#333333",
            "background": "#ffffff",
            "surface": "#f5f5f5",
            "border": "#e0e0e0",
        },
    })

    results = []

    for case_id in edge_cases:
        print(f"\n测试案例: {case_id}")
        print("-" * 80)

        try:
            # 获取案例配置
            entry = get_catalog_entry(case_id)

            # 构建请求
            content = BenchmarkSlideContent(
                key_points=list(entry.key_points) if entry.key_points else None,
                metrics=list(entry.metrics) if entry.metrics else None,
                captions=list(entry.captions) if entry.captions else None,
                insight=entry.insight,
                hero_asset_id=entry.hero_asset_id,
                supporting_asset_ids=list(entry.supporting_asset_ids) if entry.supporting_asset_ids else None,
                dominant_content_type=entry.dominant_content_type,
                preferred_layout_families=list(entry.preferred_layout_families) if entry.preferred_layout_families else None,
                drawing_hero=entry.drawing_hero,
            )

            request = BenchmarkCaseBuildRequest(
                definition=entry.definition,
                design_system=design_system,
                title=entry.slide_title,
                message=entry.message,
                visual_requirements=[],
                content=content,
                source_page=entry.source_page,
                source_document=entry.source_document,
            )

            # 执行 Benchmark
            result = service.build_case(request)

            # 输出结果
            print(f"标题: {entry.slide_title}")
            print(f"布局族: {result.plan.layout_family.value}")
            print(f"变体: {result.plan.variant}")
            print(f"规则验证: {'✓ 通过' if result.rule_score.passed else '✗ 失败'}")
            print(f"布局得分: {result.rule_score.layout_score:.3f}")
            print(f"阻塞问题数: {result.rule_score.blocking_issue_count}")

            if result.report.issues:
                print(f"问题列表:")
                for issue in result.report.issues:
                    print(f"  - [{issue.severity.value}] {issue.rule_code}: {issue.message}")

            results.append({
                "case_id": case_id,
                "passed": result.rule_score.passed,
                "score": result.rule_score.layout_score,
                "issues": len(result.report.issues),
            })

        except Exception as e:
            print(f"✗ 执行失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "case_id": case_id,
                "passed": False,
                "score": 0.0,
                "error": str(e),
            })

    # 汇总结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)

    passed_count = sum(1 for r in results if r.get("passed", False))
    total_count = len(results)

    print(f"\n通过率: {passed_count}/{total_count} = {passed_count/total_count*100:.1f}%")
    print(f"\n详细结果:")

    for r in results:
        status = "✓ 通过" if r.get("passed", False) else "✗ 失败"
        score = r.get("score", 0.0)
        issues = r.get("issues", 0)
        error = r.get("error", "")

        print(f"  {r['case_id']}: {status} (得分: {score:.3f}, 问题数: {issues})")
        if error:
            print(f"    错误: {error}")

    # 分析边界案例特点
    print("\n" + "=" * 80)
    print("边界案例分析")
    print("=" * 80)

    print("\n1. edge_031_minimal_content（极少内容）")
    print("   挑战: 仅标题，无要点，无素材")
    print("   期望: 留白充足但不空旷")

    print("\n2. edge_032_excessive_content（极多内容）")
    print("   挑战: 10+ 要点，多个指标")
    print("   期望: 合理组织，避免拥挤")

    print("\n3. edge_033_no_assets（无素材）")
    print("   挑战: 纯文字，无图片")
    print("   期望: 文字层次清晰，排版舒适")

    print("\n4. edge_034_conflicting_assets（冲突素材）")
    print("   挑战: 横向照片 + 竖向立面图混合")
    print("   期望: 合理布局，避免变形")

    print("\n" + "=" * 80)

    return results


if __name__ == "__main__":
    results = test_edge_cases()

    # 返回退出码
    passed = all(r.get("passed", False) for r in results)
    sys.exit(0 if passed else 1)
