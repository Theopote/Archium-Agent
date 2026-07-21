"""Extract ArchitecturalContentSchema from induced representative slides."""

from __future__ import annotations

from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRequirement,
    ContentRole,
    EvidenceRequirement,
    VisualRequirement,
)
from archium.domain.visual.reference_slide import (
    ReferenceElementType,
    ReferencePresentation,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    ReferenceSlideCluster,
    TemplateInductionResult,
)

_PURPOSE_BY_CONTENT: dict[ArchitecturalContentType, str] = {
    ArchitecturalContentType.DRAWING_FOCUS: "解释项目总体空间结构与关键图纸信息",
    ArchitecturalContentType.PHOTO_ANALYSIS: "用现场照片与判断证明存在明确空间或运营问题",
    ArchitecturalContentType.CASE_COMPARISON: "通过案例对比支撑当前策略选择",
    ArchitecturalContentType.BEFORE_AFTER: "展示改造前后差异以证明方案效果",
    ArchitecturalContentType.METRIC_SUMMARY: "汇总关键指标并支持决策判断",
    ArchitecturalContentType.STRATEGY: "提出可执行的空间或运营策略",
    ArchitecturalContentType.PROCESS: "说明实施流程或阶段路径",
    ArchitecturalContentType.TIMELINE: "交代时间节奏与关键里程碑",
    ArchitecturalContentType.DIAGRAM: "用图解说明关系、流线或系统结构",
    ArchitecturalContentType.TEXT_ARGUMENT: "用文字论证推进核心主张",
    ArchitecturalContentType.IMAGE_TEXT_HYBRID: "图文结合说明判断与证据",
    ArchitecturalContentType.MULTI_IMAGE_GRID: "以多图证据板组织现场或成果观察",
    ArchitecturalContentType.COVER_VISUAL: "建立项目主题与汇报开场印象",
    ArchitecturalContentType.SECTION_VISUAL: "分隔章节并预告下一论证段落",
    ArchitecturalContentType.CONCLUSION: "收束结论并指向决策或行动",
    ArchitecturalContentType.UNKNOWN: "完成该类页面的沟通任务（待人工确认用途）",
}

_AUDIENCE_BY_FUNCTIONAL: dict[FunctionalSlideType, str] = {
    FunctionalSlideType.COVER: "建立专业可信开场",
    FunctionalSlideType.AGENDA: "让受众掌握汇报结构",
    FunctionalSlideType.SECTION_DIVIDER: "切换论证段落",
    FunctionalSlideType.EXECUTIVE_SUMMARY: "快速抓住核心结论",
    FunctionalSlideType.DECISION: "明确需要批准的事项",
    FunctionalSlideType.CONTENT: "理解证据与判断",
    FunctionalSlideType.CLOSING: "结束汇报并保留专业印象",
    FunctionalSlideType.APPENDIX: "查阅补充材料",
    FunctionalSlideType.UNKNOWN: "待确认受众效果",
}


class ArchitecturalContentSchemaExtractor:
    """Heuristic schema induction from representative reference slides."""

    def extract_for_induction(
        self,
        presentation: ReferencePresentation,
        induction: TemplateInductionResult,
    ) -> list[ArchitecturalContentSchema]:
        by_id = {s.slide_id: s for s in presentation.slides}
        schemas: list[ArchitecturalContentSchema] = []
        for cluster in induction.clusters:
            slide_id = cluster.representative_slide_id
            slide = by_id.get(slide_id)
            if slide is None and cluster.slide_ids:
                slide = by_id.get(cluster.slide_ids[0])
            if slide is None:
                continue
            schemas.append(self.extract_from_slide(slide, cluster=cluster))
        return schemas

    def extract_from_slide(
        self,
        slide: ReferenceSlideSnapshot,
        *,
        cluster: ReferenceSlideCluster,
    ) -> ArchitecturalContentSchema:
        text_len = slide.text_length
        image_count = sum(
            1
            for e in slide.elements
            if e.element_type == ReferenceElementType.IMAGE
        )
        drawing_count = sum(
            1
            for e in slide.elements
            if e.element_type == ReferenceElementType.DRAWING or e.semantic_role == "drawing"
        )
        metric_count = sum(1 for e in slide.elements if e.semantic_role == "metric")
        caption_count = sum(1 for e in slide.elements if e.semantic_role == "caption")
        source_count = sum(1 for e in slide.elements if e.semantic_role == "source")
        body_count = sum(1 for e in slide.elements if e.semantic_role in {"body", "subtitle"})

        content_type = cluster.content_type
        functional = cluster.functional_type
        evidence: list[str] = [
            f"representative={slide.slide_id}",
            f"content_type={content_type.value}",
            f"images={image_count}",
            f"drawings={drawing_count}",
            f"metrics={metric_count}",
            f"text_len={text_len}",
        ]

        required_content: list[ContentRequirement] = [
            ContentRequirement(
                role=ContentRole.TITLE,
                required=True,
                min_count=1,
                max_count=1,
                min_length=4,
                max_length=60,
                semantic_description="结论式标题，不得只写栏目名",
            )
        ]
        optional_content: list[ContentRequirement] = []
        visual: list[VisualRequirement] = []
        evidence_reqs: list[EvidenceRequirement] = []
        constraints: list[str] = []

        central_claim = functional == FunctionalSlideType.CONTENT
        citation_required = source_count > 0 or content_type in {
            ArchitecturalContentType.DRAWING_FOCUS,
            ArchitecturalContentType.METRIC_SUMMARY,
            ArchitecturalContentType.CASE_COMPARISON,
        }
        caption_required = caption_count > 0 or drawing_count > 0 or image_count >= 2
        metric_unit_required = metric_count > 0 or content_type == ArchitecturalContentType.METRIC_SUMMARY
        supports_drawing = drawing_count > 0 or content_type == ArchitecturalContentType.DRAWING_FOCUS

        if central_claim:
            required_content.append(
                ContentRequirement(
                    role=ContentRole.CENTRAL_CLAIM,
                    required=True,
                    min_count=1,
                    max_count=1,
                    min_length=8,
                    max_length=120,
                    semantic_description="一句综合判断或中心主张",
                )
            )

        if body_count or content_type in {
            ArchitecturalContentType.TEXT_ARGUMENT,
            ArchitecturalContentType.STRATEGY,
            ArchitecturalContentType.PROCESS,
        }:
            required_content.append(
                ContentRequirement(
                    role=ContentRole.BODY,
                    required=True,
                    min_count=1,
                    max_count=max(body_count, 3),
                    min_length=10,
                    max_length=280,
                    semantic_description="支撑主张的正文要点",
                )
            )

        if metric_count or content_type == ArchitecturalContentType.METRIC_SUMMARY:
            required_content.append(
                ContentRequirement(
                    role=ContentRole.METRIC,
                    required=True,
                    min_count=max(1, min(metric_count, 3)),
                    max_count=max(metric_count, 6),
                    min_length=2,
                    max_length=40,
                    semantic_description="带单位的关键指标",
                )
            )
            constraints.append("指标必须有单位")

        if caption_required:
            required_content.append(
                ContentRequirement(
                    role=ContentRole.CAPTION,
                    required=True,
                    min_count=1,
                    max_count=max(caption_count, image_count + drawing_count, 1),
                    min_length=2,
                    max_length=80,
                    semantic_description="说明图片/图纸观察点的图注",
                )
            )

        if citation_required:
            required_content.append(
                ContentRequirement(
                    role=ContentRole.SOURCE,
                    required=True,
                    min_count=1,
                    max_count=2,
                    min_length=2,
                    max_length=80,
                    semantic_description="可追溯来源",
                )
            )

        if functional == FunctionalSlideType.DECISION:
            required_content.append(
                ContentRequirement(
                    role=ContentRole.DECISION_REQUEST,
                    required=True,
                    min_count=1,
                    max_count=3,
                    min_length=6,
                    max_length=120,
                    semantic_description="提请批准或确认的事项",
                )
            )

        # Visual requirements — distinguish drawing vs photo.
        if supports_drawing:
            visual.append(
                VisualRequirement(
                    role="drawing",
                    required=True,
                    min_count=1,
                    max_count=max(drawing_count, 1),
                    fit_mode="contain",
                    description="图纸必须 contain，不得裁切关键边界",
                )
            )
            evidence_reqs.append(
                EvidenceRequirement(
                    evidence_type="drawing",
                    required=True,
                    min_count=1,
                    max_count=max(drawing_count, 2),
                    description="项目图纸，禁止用参考模板图冒充",
                )
            )
            constraints.append("图纸文字需达到可读阈值")
            constraints.append("不得将 Drawing 改为 cover 裁切")

        if content_type == ArchitecturalContentType.PHOTO_ANALYSIS:
            visual.append(
                VisualRequirement(
                    role="supporting_image",
                    required=True,
                    min_count=2,
                    max_count=max(image_count, 4),
                    fit_mode="cover",
                    description="项目现场照片证据",
                )
            )
            evidence_reqs.append(
                EvidenceRequirement(
                    evidence_type="project_photo",
                    required=True,
                    min_count=2,
                    max_count=4,
                    must_be_observable_in_asset=True,
                    description="每个问题必须能从图片中观察到",
                )
            )
            required_content.append(
                ContentRequirement(
                    role=ContentRole.EVIDENCE,
                    required=True,
                    min_count=2,
                    max_count=4,
                    min_length=4,
                    max_length=60,
                    semantic_description="问题证据标签",
                )
            )
            constraints.append("只能使用项目现场照片")
            constraints.append("不允许使用参考案例图片")
            constraints.append("不允许使用 AI 生成图片冒充现场")

        if content_type == ArchitecturalContentType.BEFORE_AFTER:
            visual.append(
                VisualRequirement(
                    role="before_after_pair",
                    required=True,
                    min_count=2,
                    max_count=2,
                    fit_mode="cover",
                    description="改造前/后对照图",
                )
            )

        if content_type == ArchitecturalContentType.CASE_COMPARISON:
            visual.append(
                VisualRequirement(
                    role="supporting_image",
                    required=True,
                    min_count=2,
                    max_count=max(image_count, 4),
                    fit_mode="cover",
                    description="对标案例图",
                )
            )
            evidence_reqs.append(
                EvidenceRequirement(
                    evidence_type="reference_case",
                    required=True,
                    min_count=1,
                    max_count=2,
                    description="明确标注为参考案例，不得冒充本项目",
                )
            )
            constraints.append("参考案例素材必须保持 reference_case 来源")

        if content_type == ArchitecturalContentType.MULTI_IMAGE_GRID:
            visual.append(
                VisualRequirement(
                    role="multi_image_grid",
                    required=True,
                    min_count=4,
                    max_count=max(image_count, 8),
                    fit_mode="cover",
                    description="多图网格证据板",
                )
            )

        if image_count > 0 and not visual:
            visual.append(
                VisualRequirement(
                    role="hero_image" if image_count == 1 else "supporting_image",
                    required=True,
                    min_count=1,
                    max_count=max(image_count, 1),
                    fit_mode="cover",
                    description="页面主视觉或支撑图",
                )
            )

        # Asset origin policy by page type.
        if content_type == ArchitecturalContentType.PHOTO_ANALYSIS:
            allowed = ["project_upload"]
            forbidden = ["reference_template", "reference_case", "ai_generated", "stock_image"]
        elif content_type == ArchitecturalContentType.CASE_COMPARISON:
            allowed = ["reference_case", "public_research"]
            forbidden = ["reference_template", "ai_generated"]
        elif supports_drawing:
            allowed = ["project_upload"]
            forbidden = ["reference_template", "ai_generated", "stock_image"]
        else:
            allowed = ["project_upload", "public_research"]
            forbidden = ["reference_template", "ai_generated"]

        if content_type == ArchitecturalContentType.UNKNOWN or functional == FunctionalSlideType.UNKNOWN:
            needs_review = True
            confidence = 0.35
            evidence.append("unknown type — needs human schema confirmation")
        else:
            needs_review = False
            confidence = min(0.95, 0.55 + 0.1 * len(required_content) + 0.05 * len(visual))

        name = f"{functional.value}/{content_type.value}"
        purpose = _PURPOSE_BY_CONTENT.get(
            content_type, _PURPOSE_BY_CONTENT[ArchitecturalContentType.UNKNOWN]
        )
        if functional != FunctionalSlideType.CONTENT:
            purpose = f"{_AUDIENCE_BY_FUNCTIONAL.get(functional, '')}；{purpose}".strip("；")

        min_assets = 0
        max_assets = 8
        if visual:
            min_assets = sum(v.min_count for v in visual if v.required)
            max_assets = max(sum(v.max_count for v in visual), min_assets, image_count + drawing_count)

        return ArchitecturalContentSchema(
            name=name,
            cluster_id=cluster.id,
            representative_slide_id=slide.slide_id,
            functional_type=functional,
            content_type=content_type,
            page_purpose=purpose,
            audience_effect=_AUDIENCE_BY_FUNCTIONAL.get(functional, ""),
            central_claim_required=central_claim,
            required_content=required_content,
            optional_content=optional_content,
            visual_requirements=visual,
            evidence_requirements=evidence_reqs,
            allowed_asset_origins=allowed,
            forbidden_asset_origins=forbidden,
            min_text_length=max(20, min(text_len // 2, 80)) if text_len else 0,
            max_text_length=max(400, text_len + 200),
            min_asset_count=min_assets,
            max_asset_count=max_assets,
            supports_drawing=supports_drawing,
            allowed_drawing_types=["site_plan", "floor_plan", "section", "elevation"]
            if supports_drawing
            else [],
            citation_required=citation_required,
            caption_required=caption_required,
            metric_unit_required=metric_unit_required,
            architectural_constraints=constraints,
            extraction_evidence=evidence,
            confidence=round(confidence, 3),
            needs_review=needs_review,
        )
