"""静态代码审查：验证 E2E Benchmark 修复的正确性

不需要运行代码，只检查代码结构和 API 调用
"""

import re
from pathlib import Path


def check_file_exists(file_path: Path) -> bool:
    """检查文件是否存在"""
    if file_path.exists():
        print(f"✅ 文件存在: {file_path.name}")
        return True
    else:
        print(f"❌ 文件不存在: {file_path}")
        return False


def check_imports(content: str) -> dict:
    """检查导入语句"""
    results = {
        "ProjectRepository": "ProjectRepository" in content,
        "PresentationRepository": "PresentationRepository" in content,
        "LayoutPlanRepository": "LayoutPlanRepository" in content,
        "DesignSystemRepository": "DesignSystemRepository" in content,
        "IngestionService": "IngestionService" in content,
    }

    print("\n【导入检查】")
    for name, found in results.items():
        status = "✅" if found else "❌"
        print(f"{status} {name}")

    return results


def check_removed_wrong_apis(content: str) -> dict:
    """检查是否移除了错误的 API 调用"""
    wrong_apis = {
        "import_from_files": "import_from_files(" in content,  # 应该不存在
        "get_layout_plan": "self._presentations.get_layout_plan(" in content,  # 应该不存在
        "presentation.design_system": "presentation.design_system" in content,  # 应该不存在
    }

    print("\n【错误 API 检查（应该已移除）】")
    all_removed = True
    for api, found in wrong_apis.items():
        if found:
            print(f"❌ 仍在使用错误的 API: {api}")
            all_removed = False
        else:
            print(f"✅ 已移除错误 API: {api}")

    return {"all_removed": all_removed}


def check_correct_apis(content: str) -> dict:
    """检查是否使用了正确的 API"""
    correct_apis = {
        "import_file": "import_file(" in content,
        "LayoutPlanRepository.get": "self._layout_plans.get(" in content,
        "DesignSystemRepository": "self._design_systems" in content,
        "ProjectRepository.create": "self._projects.create(" in content,
    }

    print("\n【正确 API 检查（应该存在）】")
    for api, found in correct_apis.items():
        status = "✅" if found else "❌"
        print(f"{status} {api}")

    return correct_apis


def check_helper_method(content: str) -> bool:
    """检查是否添加了辅助方法"""
    has_method = "def _create_slides_from_case(" in content

    print("\n【辅助方法检查】")
    if has_method:
        print("✅ 添加了 _create_slides_from_case() 方法")
    else:
        print("❌ 缺少 _create_slides_from_case() 方法")

    return has_method


def check_documentation(content: str) -> bool:
    """检查是否添加了文档注释"""
    has_limitation_note = "E2E Lite" in content or "简化版本" in content

    print("\n【文档注释检查】")
    if has_limitation_note:
        print("✅ 添加了局限性说明")
    else:
        print("❌ 缺少局限性说明")

    return has_limitation_note


def check_init_repositories(content: str) -> bool:
    """检查 __init__ 方法是否初始化了所有 Repository"""
    init_section = re.search(r"def __init__\(.*?\):(.*?)(?=\n    def )", content, re.DOTALL)

    print("\n【Repository 初始化检查】")
    if not init_section:
        print("❌ 找不到 __init__ 方法")
        return False

    init_content = init_section.group(1)
    required_repos = {
        "_projects": "ProjectRepository" in init_content,
        "_presentations": "PresentationRepository" in init_content,
        "_layout_plans": "LayoutPlanRepository" in init_content,
        "_design_systems": "DesignSystemRepository" in init_content,
        "_ingestion": "IngestionService" in init_content,
    }

    all_initialized = True
    for repo, initialized in required_repos.items():
        status = "✅" if initialized else "❌"
        print(f"{status} {repo}")
        if not initialized:
            all_initialized = False

    return all_initialized


def analyze_file(file_path: Path) -> dict:
    """分析文件内容"""
    if not file_path.exists():
        return {"exists": False}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "exists": True,
        "imports": check_imports(content),
        "wrong_apis_removed": check_removed_wrong_apis(content),
        "correct_apis": check_correct_apis(content),
        "helper_method": check_helper_method(content),
        "documentation": check_documentation(content),
        "init_repositories": check_init_repositories(content),
    }


def main():
    """运行静态分析"""
    print("=" * 70)
    print("E2E Benchmark Service 修复验证（静态代码审查）")
    print("=" * 70)

    service_file = Path("/sessions/relaxed-wizardly-brahmagupta/mnt/Archium-Agent/archium/application/visual/e2e_benchmark_service.py")

    print(f"\n目标文件: {service_file}")
    print("-" * 70)

    if not check_file_exists(service_file):
        print("\n❌ 文件不存在，无法继续检查")
        return

    print("\n" + "=" * 70)
    print("开始详细检查")
    print("=" * 70)

    results = analyze_file(service_file)

    # 汇总结果
    print("\n" + "=" * 70)
    print("检查总结")
    print("=" * 70)

    checks = [
        ("文件存在", results["exists"]),
        ("导入正确", all(results["imports"].values())),
        ("错误 API 已移除", results["wrong_apis_removed"]["all_removed"]),
        ("正确 API 已使用", all(results["correct_apis"].values())),
        ("辅助方法已添加", results["helper_method"]),
        ("文档注释完整", results["documentation"]),
        ("Repository 初始化", results["init_repositories"]),
    ]

    passed = sum(1 for _, result in checks if result)
    total = len(checks)

    print()
    for name, result in checks:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    print()
    print(f"通过率: {passed}/{total} ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n" + "🎉" * 35)
        print("所有检查通过！E2E Benchmark Service 修复验证成功！")
        print("🎉" * 35)
        print("\n修复要点:")
        print("  ✅ 使用正确的 IngestionService.import_file() API")
        print("  ✅ 使用 LayoutPlanRepository 获取布局计划")
        print("  ✅ 使用 DesignSystemRepository 加载设计系统")
        print("  ✅ 补充了 Project 创建和 Presentation 创建流程")
        print("  ✅ 添加了 _create_slides_from_case() 辅助方法")
        print("  ✅ 标注了当前实现的局限性（E2E Lite）")
        print("\n下一步:")
        print("  📋 Phase 2: 补充 Brief → Storyline 生成")
        print("  📋 Phase 2: 集成完整 Visual Workflow")
        print("  📋 Phase 3: 实现真正的端到端验证")
    else:
        print(f"\n⚠️  有 {total - passed} 个检查失败")
        print("\n建议:")
        for name, result in checks:
            if not result:
                print(f"  - 修复: {name}")


if __name__ == "__main__":
    main()
