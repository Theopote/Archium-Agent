"""Default outline section templates for real architectural scenarios."""

from __future__ import annotations

from archium.domain.outline import OutlineSection

CulturalVillageSection = OutlineSection  # alias for readability
RenovationSection = OutlineSection


def _section(
    section_id: str,
    title: str,
    purpose: str,
    key_message: str,
    *,
    order: int,
    slides: int = 1,
    category: str = "general",
    evidence: list[str] | None = None,
    assets: list[str] | None = None,
    required: bool = True,
) -> OutlineSection:
    return OutlineSection(
        id=section_id,
        title=title,
        purpose=purpose,
        key_message=key_message,
        order=order,
        estimated_slide_count=slides,
        category=category,
        evidence_requirements=evidence or [],
        required_assets=assets or [],
        required=required,
        expanded=True,
    )


def cultural_village_outline_sections() -> list[OutlineSection]:
    """Default structure for 文化名村文化传播与保护提升汇报."""
    specs = [
        ("cover", "封面", "intro", "确立汇报主题与对象", 0, 1),
        ("purpose", "汇报目的", "intro", "说明为何开展保护与传播提升", 1, 1),
        ("overview", "村庄基本情况", "context", "介绍名村基本身份与现状", 2, 1),
        ("location", "区位与区域文化关系", "context", "说明村庄在区域文化格局中的位置", 3, 1),
        ("history", "历史沿革", "heritage", "梳理可验证的历史脉络", 4, 1),
        ("name_story", "村名与故事来源", "heritage", "解释村名与核心故事来源", 5, 1),
        ("value", "村庄文化价值", "heritage", "提炼文化价值与保护意义", 6, 1),
        ("spatial_pattern", "传统空间格局", "heritage", "说明传统空间结构特征", 7, 1),
        ("public_space", "街巷与公共空间", "heritage", "分析街巷与公共生活空间", 8, 1),
        ("architecture", "代表性传统建筑", "heritage", "展示代表性建筑与价值", 9, 2),
        ("clan_culture", "历史人物与宗族文化", "heritage", "关联人物、宗族与文化记忆", 10, 1),
        ("intangible", "民俗、节庆与非遗", "culture", "呈现活态文化与非遗资源", 11, 1),
        ("awareness_issue", "当前文化认知问题", "problem", "指出外部认知不足问题", 12, 1),
        ("space_issue", "当前空间环境问题", "problem", "指出空间环境与使用问题", 13, 1),
        ("communication_issue", "文化传播问题", "problem", "指出传播渠道与品牌问题", 14, 1),
        ("goals", "总体提升目标", "strategy", "提出保护传播总体目标", 15, 1),
        ("brand", "文化品牌定位", "strategy", "明确品牌定位与传播主张", 16, 1),
        ("storyline", "村庄核心故事线", "strategy", "形成对外可理解的故事主线", 17, 1),
        ("route", "文化游览路径", "strategy", "组织游览路径与体验节点", 18, 1),
        ("space_upgrade", "重点空间提升", "strategy", "对应具体空间提升策略", 19, 1),
        ("building_conservation", "建筑保护与适应性更新", "strategy", "说明建筑保护与更新原则", 20, 1),
        ("signage", "标识导视系统", "implementation", "提出导视与识别系统", 21, 1),
        ("events", "节庆与公共活动", "implementation", "策划公共活动与节庆机制", 22, 1),
        ("media", "文创与媒体传播", "implementation", "提出文创与媒体传播路径", 23, 1),
        ("operation", "运营机制与分期实施", "implementation", "说明运营与分期安排", 24, 1),
        ("benefits", "预期文化、社会和经济效益", "decision", "说明预期综合效益", 25, 1),
        ("summary", "总结与决策事项", "decision", "汇总结论与需决策事项", 26, 1),
    ]
    return [
        _section(sid, title, cat, msg, order=order, slides=slides)
        for sid, title, cat, msg, order, slides in specs
    ]


def renovation_outline_sections() -> list[OutlineSection]:
    """Default structure for 老旧建筑改造提升汇报."""
    specs = [
        ("cover", "封面", "intro", "明确改造项目与汇报对象", 0, 1),
        ("background", "项目背景", "context", "说明项目背景与改造必要性", 1, 1),
        ("location", "区位与周边条件", "context", "分析区位与周边环境", 2, 1),
        ("history", "建筑历史与现状", "context", "梳理建筑历史与现状", 3, 1),
        ("function", "使用功能现状", "context", "说明当前功能与使用状况", 4, 1),
        ("circulation_issue", "交通问题", "problem", "指出现状交通与流线问题", 5, 1),
        ("space_issue", "空间问题", "problem", "指出空间布局与使用问题", 6, 1),
        ("facade_issue", "立面问题", "problem", "指出现状立面问题", 7, 1),
        ("landscape_issue", "环境与景观问题", "problem", "指出环境与景观问题", 8, 1),
        ("structure", "结构与设备现状", "technical", "说明结构与设备现状", 9, 1),
        ("fire_safety", "消防与安全风险", "technical", "提示消防与安全风险", 10, 1),
        ("user_needs", "使用者需求", "context", "归纳使用者与甲方需求", 11, 1),
        ("value", "改造价值判断", "strategy", "论证改造价值与必要性", 12, 1),
        ("goals", "改造目标", "strategy", "明确改造目标", 13, 1),
        ("strategy", "总体设计策略", "strategy", "提出总体设计策略", 14, 1),
        ("program", "功能重组", "strategy", "说明功能重组方案", 15, 1),
        ("circulation", "交通优化", "strategy", "提出交通与流线优化", 16, 1),
        ("public_space", "公共空间提升", "strategy", "提出公共空间提升策略", 17, 1),
        ("facade", "立面更新", "strategy", "说明立面更新策略", 18, 1),
        ("interior", "室内环境提升", "strategy", "提出室内环境改善", 19, 1),
        ("landscape", "景观与夜景", "strategy", "提出景观与夜景策略", 20, 1),
        ("energy", "节能与设备更新", "technical", "说明节能与设备更新建议", 21, 1),
        ("accessibility", "无障碍与适老化", "technical", "提出无障碍与适老化措施", 22, 1),
        ("feasibility", "结构、消防和技术可行性建议", "technical", "提示专业核查事项", 23, 1),
        ("before_after", "改造前后对比", "strategy", "展示改造前后关系", 24, 1),
        ("phasing", "分期实施", "implementation", "说明分期实施安排", 25, 1),
        ("investment", "投资优先级", "decision", "提出投资优先级建议", 26, 1),
        ("benefits", "预期效益", "decision", "说明预期综合效益", 27, 1),
        ("decisions", "决策事项", "decision", "列出需决策事项", 28, 1),
        ("summary", "总结", "decision", "总结汇报结论", 29, 1),
    ]
    return [
        _section(sid, title, cat, msg, order=order, slides=slides)
        for sid, title, cat, msg, order, slides in specs
    ]


def detect_scenario_template(
    *,
    required_sections: list[str] | None = None,
    purpose: str = "",
    audience: str = "",
) -> str | None:
    """Heuristically pick a default template key."""
    text = " ".join(required_sections or []) + purpose + audience
    culture_markers = ("文化", "名村", "遗产", "非遗", "村落", "传播", "保护提升")
    renovation_markers = ("改造", "老旧", "更新", " retrofit", "厂房", "现状问题")
    if any(marker in text for marker in culture_markers):
        return "cultural_village"
    if any(marker in text for marker in renovation_markers):
        return "renovation"
    return None


def template_sections(template_key: str) -> list[OutlineSection]:
    if template_key == "cultural_village":
        return cultural_village_outline_sections()
    if template_key == "renovation":
        return renovation_outline_sections()
    raise ValueError(f"Unknown outline template: {template_key}")
