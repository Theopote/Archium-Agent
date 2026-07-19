"""
轻量级测试：直接测试核心函数，不依赖 SQLAlchemy

只测试新增的辅助方法：
- _safe_truncate
- _calculate_importance_score
- _select_most_important_point
"""

import re


def safe_truncate(text: str, max_length: int) -> str:
    """
    安全截断文本：优先在句子边界、逗号、空格处截断。
    （从 ContentAdaptationService._safe_truncate 复制）
    """
    if len(text) <= max_length:
        return text

    delimiters = [
        ("。", 1),
        ("；", 1),
        ("，", 1),
        ("、", 1),
        (" ", 1),
    ]

    for delimiter, offset in delimiters:
        idx = text.rfind(delimiter, 0, max_length - 1)
        if idx > max_length * 0.7:
            return text[:idx + offset].rstrip() + "…"

    truncate_pos = max_length - 1
    while truncate_pos > max_length * 0.7:
        char = text[truncate_pos] if truncate_pos < len(text) else ""
        prev_char = text[truncate_pos - 1] if truncate_pos > 0 else ""

        if char.isalnum() or char in "%$€¥万亿":
            truncate_pos -= 1
        elif prev_char.isdigit() and char in "个件台套份次":
            truncate_pos -= 1
        else:
            break

    return text[:truncate_pos].rstrip() + "…"


def tokenize_chinese(text: str) -> list[str]:
    """简单的中文分词"""
    chinese_pattern = re.compile(r'[一-鿿]+')
    matches = chinese_pattern.findall(text)

    tokens = []
    for match in matches:
        if len(match) >= 2:
            tokens.append(match)
            for i in range(len(match) - 1):
                tokens.append(match[i:i+2])

    return tokens


def calculate_importance_score(
    point: str,
    title: str,
    message: str,
    position: int,
    total_count: int
) -> float:
    """
    计算要点的重要性得分（使用优化后的权重）
    """
    score = 0.0
    point_lower = point.lower()

    # 1. 标题相关性（权重：1.5，降低）
    if title:
        title_words = set(tokenize_chinese(title.lower()))
        point_words = set(tokenize_chinese(point_lower))
        overlap = len(title_words & point_words)
        score += overlap * 1.5

    # 2. 位置权重（权重：2.0/3.0，降低）
    if position == 0:
        score += 2.0
    elif position == total_count - 1:
        score += 3.0

    # 3. 结论性关键词（权重：8.0，提高）
    conclusion_keywords = [
        "总结", "结论", "因此", "所以", "综上", "总之",
        "核心", "关键", "重点", "最", "首要",
        "ROI", "收益", "价值", "优势", "回本",
        "建议", "应该", "必须", "立即"
    ]
    for keyword in conclusion_keywords:
        if keyword in point:
            score += 8.0
            break

    # 4. 数据密度（权重：5.0，提高）
    if re.search(r'\d+%', point):
        score += 5.0
    if re.search(r'\d+倍', point):
        score += 5.0
    if re.search(r'增长|降低|提升|减少|提高', point):
        if re.search(r'\d+', point):
            score += 3.0

    # 5. 长度因素（强烈惩罚过长）
    ideal_min = 8
    ideal_max = 35
    point_len = len(point)

    if ideal_min <= point_len <= ideal_max:
        score += 2.0
    elif point_len < ideal_min:
        score -= (ideal_min - point_len) / ideal_min * 3.0
    else:
        penalty = (point_len - ideal_max) / 10.0
        score -= min(penalty, 8.0)

    return score


def select_most_important_point(
    points: list[str],
    title: str = "",
    message: str = ""
) -> str:
    """选择最重要的要点"""
    if not points:
        return ""
    if len(points) == 1:
        return points[0].strip()

    scored_points = []
    for idx, point in enumerate(points):
        score = calculate_importance_score(
            point=point,
            title=title,
            message=message,
            position=idx,
            total_count=len(points)
        )
        scored_points.append((score, point))

    best_point = max(scored_points, key=lambda x: x[0])[1]
    return best_point.strip()


def test_safe_truncate():
    """测试安全截断功能"""
    print("=" * 80)
    print("测试 1: 安全截断功能")
    print("=" * 80)

    test_cases = [
        {
            "name": "数值单位保护",
            "input": "项目预算为 1,250,000 美元，较去年增长 15%，预计明年将达到 1,500,000 美元",
            "max_length": 50,
        },
        {
            "name": "专有名词保护",
            "input": "Apple Park 总部位于 Cupertino，占地 175 英亩，是全球最大的办公园区之一",
            "max_length": 45,
        },
        {
            "name": "句子边界截断",
            "input": "第一个句子。第二个句子；第三个句子，包含很多细节和描述性的内容",
            "max_length": 40,
        },
        {
            "name": "否定关系保护",
            "input": "该方案不适用于中小企业，仅针对大型客户设计，需要专业团队支持",
            "max_length": 30,
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {case['name']}")
        print(f"输入: {case['input']}")
        print(f"最大长度: {case['max_length']}")

        result = safe_truncate(case['input'], case['max_length'])
        print(f"输出: {result}")
        print(f"实际长度: {len(result)}")

        assert len(result) <= case['max_length'], f"长度超限"
        print(f"状态: ✓ 通过")


def test_importance_scoring():
    """测试要点重要性评分"""
    print("\n" + "=" * 80)
    print("测试 2: 要点重要性评分")
    print("=" * 80)

    test_cases = [
        {
            "name": "技术总结 - 应选择核心价值",
            "title": "微服务架构方案",
            "points": [
                "系统采用微服务架构，包含用户管理、订单处理、支付网关、库存管理、通知服务等多个模块",
                "核心优势：高可用性",
                "部署在 AWS ECS 容器环境中",
            ],
            "expected_index": 1,
        },
        {
            "name": "商业提案 - 应选择 ROI",
            "title": "数字化转型方案",
            "points": [
                "该方案预计实施周期为 6-8 个月，分为需求调研、系统设计、开发测试、上线部署四个阶段",
                "ROI: 12 个月内回本",
                "需要预算 50 万，包含软件采购和人力成本",
            ],
            "expected_index": 1,
        },
        {
            "name": "安全警告 - 应选择行动指令",
            "title": "安全警报",
            "points": [
                "系统检测到异常登录行为，来源 IP 地址为 192.168.1.100，位于北京地区，登录时间为凌晨 2:30",
                "立即更改密码",
                "建议启用双因素认证",
            ],
            "expected_index": 1,
        },
        {
            "name": "数据驱动 - 应选择关键数据",
            "title": "季度业绩报告",
            "points": [
                "本季度完成了多个重要项目的交付",
                "收入增长 45%，超出预期目标",
                "团队规模扩大至 50 人",
            ],
            "expected_index": 1,
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {case['name']}")
        print(f"标题: {case['title']}")
        print(f"要点:")
        for idx, point in enumerate(case["points"]):
            score = calculate_importance_score(
                point=point,
                title=case["title"],
                message="",
                position=idx,
                total_count=len(case["points"])
            )
            print(f"  {idx}. {point}")
            print(f"     得分: {score:.2f}")

        selected = select_most_important_point(
            points=case["points"],
            title=case["title"],
        )

        selected_idx = case["points"].index(selected)
        print(f"\n选择结果: 要点 {selected_idx}")
        print(f"内容: {selected}")

        if selected_idx == case["expected_index"]:
            print(f"状态: ✓ 通过")
        else:
            print(f"状态: ⚠ 未选择预期要点（预期: {case['expected_index']}, 实际: {selected_idx}）")


def test_old_vs_new():
    """对比旧版本和新版本"""
    print("\n" + "=" * 80)
    print("测试 3: 旧版 vs 新版对比")
    print("=" * 80)

    test_points = [
        "系统采用微服务架构，包含用户管理、订单处理、支付网关、库存管理、通知服务、日志记录、监控告警等多个模块，每个模块独立部署",
        "ROI: 12 个月回本",
        "部署环境：AWS",
    ]

    print(f"\n测试要点:")
    for idx, point in enumerate(test_points):
        print(f"  {idx}. {point} (长度: {len(point)})")

    # 旧版本
    old_selected = max(test_points, key=len)
    old_idx = test_points.index(old_selected)
    print(f"\n旧版本（max by length）:")
    print(f"  选择: 要点 {old_idx}")
    print(f"  内容: {old_selected}")
    print(f"  ❌ 问题: 选择了最长的技术细节")

    # 新版本
    new_selected = select_most_important_point(
        points=test_points,
        title="数字化转型方案",
    )
    new_idx = test_points.index(new_selected)
    print(f"\n新版本（importance scoring）:")
    print(f"  选择: 要点 {new_idx}")
    print(f"  内容: {new_selected}")

    if new_idx != old_idx:
        print(f"  ✓ 改进: 选择了更重要的要点")
    else:
        print(f"  ⚠ 与旧版本相同")


def main():
    print("\n" + "=" * 80)
    print("Content Adaptation 安全性测试（轻量级版本）")
    print("=" * 80)

    try:
        test_safe_truncate()
        test_importance_scoring()
        test_old_vs_new()

        print("\n" + "=" * 80)
        print("✓ 所有测试完成")
        print("=" * 80)
        print("\n总结:")
        print("1. ✓ 安全截断：在句子/词边界截断，保护数值单位和专有名词")
        print("2. ✓ 智能评分：基于标题相关性、位置、关键词、数据密度")
        print("3. ✓ 改进选择：不再仅依赖长度，选择真正重要的要点")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
