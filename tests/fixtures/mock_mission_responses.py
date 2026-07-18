"""Mock LLM JSON responses for project mission generation tests."""

TEMPLE_MISSION_JSON = """{
  "title": "清凉寺重建前期策划",
  "task_statement": "在三原县历史文化语境下，形成宗教建筑重建的前期策划、案例研究与概念设计汇报",
  "task_natures": ["reconstruction", "research", "planning"],
  "domains": ["heritage", "culture"],
  "intervention_scales": ["site", "building"],
  "requested_service_depths": ["preliminary_research", "concept_planning", "presentation_production"],
  "project_context": "历史上多次毁建，现有地方志与现场照片",
  "current_situation": "原建筑已不存，甲方希望重新建设，建设规模尚未明确",
  "primary_problems": ["历史形制可信度不足", "建设规模未知", "重建策略未定"],
  "desired_changes": ["形成前期策划", "完成案例研究", "输出概念汇报"],
  "in_scope": ["前期策划", "案例研究", "概念设计汇报"],
  "out_of_scope": ["施工图设计", "施工招标"],
  "stakeholders": [{"name": "甲方", "role": "业主", "concerns": ["宗教功能", "文化定位"]}],
  "decision_context": "需确定重建策略与概念方向",
  "decisions_required": ["重建策略取向", "主要宗教与公共功能"],
  "known_constraints": [
    {"name": "资料条件", "value": "部分地方志与现场照片", "source": "document", "verification_status": "extracted", "importance": "high"}
  ],
  "key_unknowns": ["用地范围", "建设规模", "宗教使用要求", "重建立场", "历史形制可信度"],
  "research_questions": ["历史形制有哪些可信依据？", "同类重建案例如何处理当代性？"],
  "design_question_summaries": ["如何在历史可信度有限条件下形成可接受的重建策略？"],
  "evaluation_criteria": [{"name": "历史可信度", "description": "策略应标注历史依据来源", "weight": 0.3}],
  "uncertainty_level": "high",
  "confidence": 0.4,
  "knowledge_gaps": [
    {"category": "area", "question": "建设规模是多少？", "why_it_matters": "影响功能配置与空间策略", "priority": "high", "blocking": false},
    {"category": "history", "question": "历史形制哪些部分具有重建依据？", "why_it_matters": "影响重建策略可信度", "priority": "high", "blocking": false}
  ],
  "assumptions": [],
  "clarifying_questions": [
    {"question": "更倾向历史复原、传统语汇新建还是当代表达？", "why_asked": "决定重建策略方向", "blocking": false, "can_assume": true, "suggested_assumption": "传统语汇新建"},
    {"question": "未来主要承担哪些宗教与公共功能？", "why_asked": "影响空间配置", "blocking": false, "can_assume": true, "suggested_assumption": "礼佛与公共文化活动"},
    {"question": "是否已有明确用地边界？", "why_asked": "影响总图范围", "blocking": false, "can_assume": false, "suggested_assumption": ""}
  ],
  "design_questions": [
    {"question": "如何在历史资料有限条件下形成可接受的重建策略？", "related_problem": "历史形制不确定", "desired_outcome": "明确重建策略比较框架"}
  ]
}"""

FIRE_STATION_MISSION_JSON = """{
  "title": "消防站新建方案前期",
  "task_statement": "在既定用地与规模条件下，开展消防站新建方案的功能策划与规范研究",
  "task_natures": ["new_build"],
  "domains": ["architecture", "transport"],
  "intervention_scales": ["site", "building"],
  "requested_service_depths": ["programming", "preliminary_research"],
  "project_context": "已有明确用地、建筑面积与高度指标",
  "current_situation": "新建消防站，指标明确",
  "primary_problems": ["功能与流线组织", "规范符合性"],
  "desired_changes": ["明确功能分区", "满足消防规范"],
  "in_scope": ["功能策划", "规范研究"],
  "out_of_scope": ["施工图设计"],
  "stakeholders": [{"name": "主管部门", "role": "业主", "concerns": ["公共安全", "响应效率"]}],
  "decision_context": "需确认功能布局与规范符合性",
  "decisions_required": ["功能分区方案"],
  "known_constraints": [
    {"name": "用地面积", "value": "8000 ㎡", "source": "document", "verification_status": "user_confirmed", "importance": "high"},
    {"name": "建筑面积", "value": "4500 ㎡", "source": "document", "verification_status": "user_confirmed", "importance": "high"},
    {"name": "建筑高度", "value": "24 m", "source": "document", "verification_status": "user_confirmed", "importance": "high"}
  ],
  "key_unknowns": [],
  "research_questions": ["消防车辆流线如何组织？"],
  "design_question_summaries": [],
  "evaluation_criteria": [{"name": "规范符合性", "description": "满足消防站设计规范", "weight": 0.4}],
  "uncertainty_level": "low",
  "confidence": 0.85,
  "knowledge_gaps": [],
  "assumptions": [],
  "clarifying_questions": [],
  "design_questions": [
    {"question": "如何在有限用地内组织车辆出动与训练功能？", "related_problem": "用地紧凑", "desired_outcome": "高效出动流线"}
  ]
}"""

FABRICATED_AREA_MISSION_JSON = """{
  "title": "错误示例",
  "task_statement": "测试编造面积",
  "task_natures": ["research"],
  "domains": ["culture"],
  "intervention_scales": ["site"],
  "requested_service_depths": ["preliminary_research"],
  "known_constraints": [
    {"name": "建筑面积", "value": "12000 ㎡", "source": "assumption", "verification_status": "user_confirmed", "importance": "high"}
  ],
  "uncertainty_level": "medium",
  "confidence": 0.5,
  "knowledge_gaps": [],
  "assumptions": [],
  "clarifying_questions": [],
  "design_questions": []
}"""

TEMPLE_REVISED_AFTER_CLARIFICATION_JSON = """{
  "title": "清凉寺重建前期策划（已澄清）",
  "task_statement": "在三原县历史文化语境下，以传统语汇新建为倾向，形成宗教建筑重建的前期策划、案例研究与概念设计汇报",
  "task_natures": ["reconstruction", "research", "planning"],
  "domains": ["heritage", "culture"],
  "intervention_scales": ["site", "building"],
  "requested_service_depths": ["preliminary_research", "concept_planning", "presentation_production"],
  "project_context": "历史上多次毁建，现有地方志与现场照片；重建策略倾向传统语汇新建",
  "current_situation": "原建筑已不存，甲方希望重新建设，建设规模尚未明确",
  "primary_problems": ["历史形制可信度不足", "建设规模未知"],
  "desired_changes": ["形成前期策划", "完成案例研究", "输出概念汇报"],
  "in_scope": ["前期策划", "案例研究", "概念设计汇报"],
  "out_of_scope": ["施工图设计", "施工招标"],
  "stakeholders": [{"name": "甲方", "role": "业主", "concerns": ["宗教功能", "文化定位"]}],
  "decision_context": "重建策略取向已倾向传统语汇新建",
  "decisions_required": ["主要宗教与公共功能确认"],
  "known_constraints": [
    {"name": "资料条件", "value": "部分地方志与现场照片", "source": "document", "verification_status": "extracted", "importance": "high"},
    {"name": "重建策略倾向", "value": "传统语汇新建", "source": "assumption", "verification_status": "inferred", "importance": "high"}
  ],
  "key_unknowns": ["用地范围", "建设规模", "历史形制可信度"],
  "research_questions": ["历史形制有哪些可信依据？"],
  "design_question_summaries": ["如何在历史可信度有限条件下形成可接受的重建策略？"],
  "evaluation_criteria": [{"name": "历史可信度", "description": "策略应标注历史依据来源", "weight": 0.3}],
  "uncertainty_level": "medium",
  "confidence": 0.55,
  "knowledge_gaps": [],
  "assumptions": [
    {"statement": "传统语汇新建", "reason": "用户采用建议假设", "scope_of_use": "clarification", "confidence": 0.6}
  ],
  "clarifying_questions": [],
  "design_questions": []
}"""
