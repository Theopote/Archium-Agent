"""Extract ArchitecturalContentSchema from induced representative slides."""

from __future__ import annotations

from collections.abc import Sequence

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
    FunctionalSlideClassification,
    FunctionalSlideType,
    ReferenceSlideCluster,
    RepresentativeSlideScore,
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


def _median(values: Sequence[int | float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _percentile(values: Sequence[int | float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct / 100.0
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _slide_counts(slide: ReferenceSlideSnapshot) -> dict[str, int]:
    image_count = sum(
        1 for e in slide.iter_elements() if e.element_type == ReferenceElementType.IMAGE
    )
    drawing_count = sum(
        1
        for e in slide.iter_elements()
        if e.element_type == ReferenceElementType.DRAWING or e.semantic_role == "drawing"
    )
    metric_count = sum(1 for e in slide.iter_elements() if e.semantic_role == "metric")
    caption_count = sum(1 for e in slide.iter_elements() if e.semantic_role == "caption")
    source_count = sum(1 for e in slide.iter_elements() if e.semantic_role == "source")
    body_count = sum(
        1 for e in slide.iter_elements() if e.semantic_role in {"body", "subtitle"}
    )
    return {
        "text_len": slide.text_length,
        "image": image_count,
        "drawing": drawing_count,
        "metric": metric_count,
        "caption": caption_count,
        "source": source_count,
        "body": body_count,
    }


def _collect_reference_paragraphs(slide: ReferenceSlideSnapshot) -> list[str]:
    """Paragraph-level text collected from the representative slide (PPTAgent-style)."""
    paragraphs: list[str] = []
    seen: set[str] = set()
    for chunk in slide.text_content:
        text = chunk.strip()
        if text and text not in seen:
            paragraphs.append(text)
            seen.add(text)
    for element in slide.iter_elements():
        if element.element_type != ReferenceElementType.TEXT:
            continue
        text = (element.text or "").strip()
        if text and text not in seen:
            paragraphs.append(text)
            seen.add(text)
    return paragraphs


def _infer_slide_purpose(
    slide: ReferenceSlideSnapshot,
    content_type: ArchitecturalContentType,
    default: str,
) -> str:
    paragraphs = _collect_reference_paragraphs(slide)
    lead = paragraphs[0] if paragraphs else ""
    if content_type == ArchitecturalContentType.PHOTO_ANALYSIS and len(lead) >= 4:
        clean = lead.strip("。．. ")
        return f"证明{clean}"
    if content_type == ArchitecturalContentType.DRAWING_FOCUS and len(lead) >= 4:
        return f"解释{lead.strip('。．. ')}"
    return default


_VISUAL_EVIDENCE_ROLES = frozenset(
    {
        "hero_image",
        "supporting_image",
        "drawing",
        "before_after_pair",
        "multi_image_grid",
    }
)


def _build_semantic_contract(
    *,
    content_type: ArchitecturalContentType,
    functional: FunctionalSlideType,
    required_content: list[ContentRequirement],
    visual: list[VisualRequirement],
    image_count: int,
    caption_count: int,
    body_count: int,
    stats: dict[str, float | int],
    claim_max: int,
    evidence_max: int,
) -> tuple[
    ContentRequirement | None,
    list[ContentRequirement],
    list[VisualRequirement],
    ContentRequirement | None,
    ContentRequirement | None,
]:
    central_claim = next(
        (item for item in required_content if item.role == ContentRole.CENTRAL_CLAIM),
        None,
    )
    evidence_items = [item for item in required_content if item.role == ContentRole.EVIDENCE]
    interpretation = next(
        (item for item in required_content if item.role == ContentRole.INTERPRETATION),
        None,
    )
    decision_request = next(
        (item for item in required_content if item.role == ContentRole.DECISION_REQUEST),
        None,
    )
    visual_evidence = [item for item in visual if item.role in _VISUAL_EVIDENCE_ROLES]

    if central_claim is None and functional == FunctionalSlideType.CONTENT:
        central_claim = ContentRequirement(
            role=ContentRole.CENTRAL_CLAIM,
            required=True,
            min_count=1,
            max_count=1,
            min_length=8,
            max_length=claim_max,
            semantic_description="一句综合判断或中心主张",
            label="问题判断",
        )

    if content_type == ArchitecturalContentType.PHOTO_ANALYSIS and not evidence_items:
        photo_min = max(2, min(int(stats.get("image_min", image_count) or 2), 4))
        evidence_items = [
            ContentRequirement(
                role=ContentRole.EVIDENCE,
                required=True,
                min_count=photo_min,
                max_count=max(4, image_count, int(stats.get("image_max", image_count))),
                min_length=4,
                max_length=evidence_max,
                semantic_description="每张现场照片对应一个可观察问题标签",
                label="照片问题标签",
            )
        ]

    if (
        content_type == ArchitecturalContentType.PHOTO_ANALYSIS
        and interpretation is None
        and (body_count > 0 or int(stats.get("text_len_p50", 0)) >= 20)
    ):
        interpretation = ContentRequirement(
            role=ContentRole.INTERPRETATION,
            required=True,
            min_count=1,
            max_count=1,
            min_length=12,
            max_length=220,
            semantic_description="综合影响或对策导向总结",
            label="综合影响",
        )

    if caption_count > 0 and content_type == ArchitecturalContentType.PHOTO_ANALYSIS:
        caption_req = next(
            (item for item in required_content if item.role == ContentRole.CAPTION),
            None,
        )
        if caption_req is not None and caption_req.label == "":
            caption_req = caption_req.model_copy(
                update={"label": "图片说明", "semantic_description": "说明图片观察点"}
            )

    return central_claim, evidence_items, visual_evidence, interpretation, decision_request


def _cluster_induction_stats(
    member_slides: list[ReferenceSlideSnapshot],
) -> dict[str, float | int]:
    if not member_slides:
        return {"member_count": 0}
    counts = [_slide_counts(slide) for slide in member_slides]
    text_lens = [c["text_len"] for c in counts]
    image_counts = [c["image"] for c in counts]
    drawing_counts = [c["drawing"] for c in counts]
    caption_rates = [1.0 if c["caption"] > 0 else 0.0 for c in counts]
    source_rates = [1.0 if c["source"] > 0 else 0.0 for c in counts]
    drawing_rates = [1.0 if c["drawing"] > 0 else 0.0 for c in counts]
    body_counts = [c["body"] for c in counts]
    return {
        "member_count": len(member_slides),
        "text_len_p10": round(_percentile(text_lens, 10)),
        "text_len_p50": round(_percentile(text_lens, 50)),
        "text_len_p90": round(_percentile(text_lens, 90)),
        "image_min": min(image_counts),
        "image_median": round(_median(image_counts)),
        "image_max": max(image_counts),
        "drawing_min": min(drawing_counts),
        "drawing_median": round(_median(drawing_counts)),
        "drawing_max": max(drawing_counts),
        "body_p90": round(_percentile(body_counts, 90)),
        "caption_rate": round(sum(caption_rates) / len(caption_rates), 3),
        "source_rate": round(sum(source_rates) / len(source_rates), 3),
        "drawing_rate": round(sum(drawing_rates) / len(drawing_rates), 3),
    }


def _role_text_lengths(
    slide: ReferenceSlideSnapshot,
    roles: set[str],
) -> list[int]:
    lengths: list[int] = []
    for element in slide.iter_elements():
        role = (element.semantic_role or "").strip().lower()
        if role in roles and element.text:
            lengths.append(len(element.text.strip()))
    return lengths


def _observed_title_length(slide: ReferenceSlideSnapshot) -> int:
    title_lens = _role_text_lengths(slide, {"title"})
    if title_lens:
        return max(title_lens)
    text_els = [
        e
        for e in slide.iter_elements()
        if e.element_type == ReferenceElementType.TEXT and (e.text or "").strip()
    ]
    if not text_els:
        return 0
    top = min(text_els, key=lambda e: (e.y, -(e.font_size_pt or 0)))
    return len(top.text.strip())


def _cluster_role_max_length(
    members: list[ReferenceSlideSnapshot],
    roles: set[str],
    *,
    floor: int,
    buffer: int = 20,
) -> int:
    lengths = [
        length
        for slide in members
        for length in _role_text_lengths(slide, roles)
    ]
    if not lengths:
        return floor
    return max(floor, max(lengths) + buffer)


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
            member_slides = [by_id[sid] for sid in cluster.slide_ids if sid in by_id]
            classification = induction.classification_for(slide.slide_id)
            rep_score = next(
                (s for s in induction.representative_scores if s.slide_id == slide.slide_id),
                None,
            )
            schemas.append(
                self.extract_from_slide(
                    slide,
                    cluster=cluster,
                    member_slides=member_slides or [slide],
                    classification=classification,
                    representative_score=rep_score,
                )
            )
        return schemas

    def extract_from_slide(
        self,
        slide: ReferenceSlideSnapshot,
        *,
        cluster: ReferenceSlideCluster,
        member_slides: list[ReferenceSlideSnapshot] | None = None,
        classification: FunctionalSlideClassification | None = None,
        representative_score: RepresentativeSlideScore | None = None,
    ) -> ArchitecturalContentSchema:
        members = member_slides or [slide]
        stats = _cluster_induction_stats(members)
        rep = _slide_counts(slide)
        text_len = int(stats.get("text_len_p50", rep["text_len"]))
        image_count = int(rep["image"])
        cluster_image_median = int(stats.get("image_median", image_count))
        cluster_image_max = int(stats.get("image_max", image_count))
        drawing_count = int(rep["drawing"])
        cluster_drawing_max = int(stats.get("drawing_max", drawing_count))
        metric_count = int(rep["metric"])
        caption_count = int(rep["caption"])
        source_count = int(rep["source"])
        body_count = int(rep["body"])
        cluster_body_p90 = int(stats.get("body_p90", body_count))

        content_type = cluster.content_type
        functional = cluster.functional_type
        evidence: list[str] = [
            f"representative={slide.slide_id}",
            f"cluster_members={stats.get('member_count', 1)}",
            f"content_type={content_type.value}",
            f"visual_layout={cluster.visual_layout_pattern.value}",
            f"images_rep={image_count}",
            f"images_cluster_median={cluster_image_median}",
            f"images_cluster_max={cluster_image_max}",
            f"drawings={drawing_count}",
            f"metrics={metric_count}",
            f"text_len_p50={text_len}",
        ]

        required_content: list[ContentRequirement] = []
        title_max = _cluster_role_max_length(members, {"title"}, floor=60)
        title_max = max(title_max, _observed_title_length(slide) + 10, 60)
        required_content.append(
            ContentRequirement(
                role=ContentRole.TITLE,
                required=True,
                min_count=1,
                max_count=1,
                min_length=4,
                max_length=title_max,
                semantic_description="结论式标题，不得只写栏目名",
            )
        )
        optional_content: list[ContentRequirement] = []
        visual: list[VisualRequirement] = []
        evidence_reqs: list[EvidenceRequirement] = []
        constraints: list[str] = []

        wants_central_claim = functional == FunctionalSlideType.CONTENT
        citation_required = (
            float(stats.get("source_rate", 0.0)) >= 0.5
            or source_count > 0
            or content_type
            in {
                ArchitecturalContentType.DRAWING_FOCUS,
                ArchitecturalContentType.METRIC_SUMMARY,
                ArchitecturalContentType.CASE_COMPARISON,
            }
        )
        if content_type in {
            ArchitecturalContentType.DRAWING_FOCUS,
            ArchitecturalContentType.METRIC_SUMMARY,
        }:
            citation_required = source_count > 0 or float(stats.get("source_rate", 0.0)) >= 0.5
        caption_required = (
            float(stats.get("caption_rate", 0.0)) >= 0.5
            or caption_count > 0
            or (drawing_count > 0 and float(stats.get("caption_rate", 0.0)) > 0)
        )
        metric_unit_required = metric_count > 0 or content_type == ArchitecturalContentType.METRIC_SUMMARY
        supports_drawing = (
            float(stats.get("drawing_rate", 0.0)) >= 0.5
            or drawing_count > 0
            or content_type == ArchitecturalContentType.DRAWING_FOCUS
        )

        if wants_central_claim:
            claim_max = _cluster_role_max_length(
                members, {"title", "body", "subtitle"}, floor=120
            )
            required_content.append(
                ContentRequirement(
                    role=ContentRole.CENTRAL_CLAIM,
                    required=True,
                    min_count=1,
                    max_count=1,
                    min_length=8,
                    max_length=claim_max,
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
                    max_count=max(cluster_body_p90, body_count, 3),
                    min_length=10,
                    max_length=280,
                    semantic_description="支撑主张的正文要点",
                )
            )

        if metric_count or content_type == ArchitecturalContentType.METRIC_SUMMARY:
            metric_max = _cluster_role_max_length(members, {"metric"}, floor=40)
            required_content.append(
                ContentRequirement(
                    role=ContentRole.METRIC,
                    required=True,
                    min_count=max(1, min(metric_count, 3)),
                    max_count=max(metric_count, 6),
                    min_length=2,
                    max_length=metric_max,
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
                    max_count=max(caption_count, cluster_image_max + cluster_drawing_max, 1),
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
                    max_count=max(drawing_count, cluster_drawing_max, 1),
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
            photo_min = max(1, min(2, int(stats.get("image_min", image_count)), image_count))
            visual.append(
                VisualRequirement(
                    role="supporting_image",
                    required=True,
                    min_count=photo_min,
                    max_count=max(cluster_image_median, image_count, 4),
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
            evidence_min = max(1, min(2, int(stats.get("body_p90", 1)), body_count or 1))
            evidence_max = _cluster_role_max_length(
                members, {"body", "caption", "subtitle"}, floor=80
            )
            required_content.append(
                ContentRequirement(
                    role=ContentRole.EVIDENCE,
                    required=True,
                    min_count=evidence_min,
                    max_count=4,
                    min_length=4,
                    max_length=evidence_max,
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
                    max_count=max(cluster_image_median, image_count, 4),
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
                    max_count=max(cluster_image_max, image_count, 8),
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
                    max_count=max(cluster_image_max, image_count, 1),
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
            classification_conf = (
                classification.confidence if classification is not None else cluster.confidence
            )
            cluster_consistency = max(
                cluster.structural_similarity,
                cluster.visual_similarity,
                cluster.semantic_similarity,
                0.45,
            )
            representative_quality = (
                representative_score.total_score if representative_score is not None else 0.6
            )
            slot_supports: list[float] = []
            if caption_required:
                slot_supports.append(float(stats.get("caption_rate", 0.0)))
            if supports_drawing:
                slot_supports.append(float(stats.get("drawing_rate", 0.0)))
            if citation_required:
                slot_supports.append(float(stats.get("source_rate", 0.0)))
            slot_support = sum(slot_supports) / len(slot_supports) if slot_supports else 0.75
            confidence = (
                classification_conf * cluster_consistency * representative_quality * slot_support
            )
            confidence = max(0.2, min(0.95, confidence))
            if int(stats.get("member_count", 1)) > 1 and image_count > cluster_image_max:
                needs_review = True
                evidence.append("representative image count above cluster max — outlier")
            if confidence < 0.45:
                needs_review = True
                evidence.append("low induction confidence — needs review")

        name = f"{functional.value}/{content_type.value}"
        purpose = _PURPOSE_BY_CONTENT.get(
            content_type, _PURPOSE_BY_CONTENT[ArchitecturalContentType.UNKNOWN]
        )
        if functional != FunctionalSlideType.CONTENT:
            purpose = f"{_AUDIENCE_BY_FUNCTIONAL.get(functional, '')}；{purpose}".strip("；")
        purpose = _infer_slide_purpose(slide, content_type, purpose)
        reference_paragraphs = _collect_reference_paragraphs(slide)
        if reference_paragraphs:
            evidence.append(f"reference_paragraphs={len(reference_paragraphs)}")

        min_assets = 0
        max_assets = 8
        if visual:
            min_assets = sum(v.min_count for v in visual if v.required)
            max_assets = max(
                sum(v.max_count for v in visual),
                min_assets,
                cluster_image_max + cluster_drawing_max,
            )

        claim_max = _cluster_role_max_length(members, {"title", "body", "subtitle"}, floor=120)
        evidence_max = _cluster_role_max_length(
            members, {"body", "caption", "subtitle"}, floor=80
        )
        central_claim, evidence_items, visual_evidence, interpretation, decision_request = (
            _build_semantic_contract(
                content_type=content_type,
                functional=functional,
                required_content=required_content,
                visual=visual,
                image_count=image_count,
                caption_count=caption_count,
                body_count=body_count,
                stats=stats,
                claim_max=claim_max,
                evidence_max=evidence_max,
            )
        )

        schema = ArchitecturalContentSchema(
            name=name,
            cluster_id=cluster.id,
            representative_slide_id=slide.slide_id,
            cluster_member_count=int(stats.get("member_count", 1)),
            functional_type=functional,
            content_type=content_type,
            visual_layout_pattern=classification.visual_layout_pattern
            if classification is not None
            else cluster.visual_layout_pattern,
            page_purpose=purpose,
            audience_effect=_AUDIENCE_BY_FUNCTIONAL.get(functional, ""),
            central_claim_required=wants_central_claim,
            reference_paragraphs=reference_paragraphs,
            central_claim=central_claim,
            evidence_items=evidence_items,
            visual_evidence=visual_evidence,
            interpretation=interpretation,
            decision_request=decision_request,
            required_content=required_content,
            optional_content=optional_content,
            visual_requirements=visual,
            evidence_requirements=evidence_reqs,
            allowed_asset_origins=allowed,
            forbidden_asset_origins=forbidden,
            min_text_length=max(20, min(int(stats.get("text_len_p10", text_len)) // 2, 80))
            if text_len
            else 0,
            max_text_length=max(400, int(stats.get("text_len_p90", text_len)) + 200),
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
            cluster_stats={k: v for k, v in stats.items() if k != "member_count"},
            confidence=round(confidence, 3),
            needs_review=needs_review,
        )
        return schema.apply_semantic_contract()
