"""Rule-based architecture slide semantic QA."""

from __future__ import annotations

import re
from uuid import UUID

from archium.application.knowledge_isolation import document_purpose_from_metadata, is_reference_document
from archium.application.renovation_issue_service import is_renovation_scenario
from archium.domain.asset import Asset
from archium.domain.document import SourceDocument
from archium.domain.enums import VisualType
from archium.domain.presentation import PresentationBrief
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.slide import SlideSpec
from archium.domain.slide_semantic_qa import (
    ArchitectureSlideSemanticQA,
    SlideSemanticCheckCode,
    SlideSemanticFinding,
)

_SKIPPABLE = {"title", "section", "closing"}
_DRAWING_TYPES = {
    VisualType.SITE_PLAN,
    VisualType.FLOOR_PLAN,
    VisualType.SECTION,
    VisualType.ELEVATION,
    VisualType.DIAGRAM,
    VisualType.MAP,
}
_DRAWING_MIN_WIDTH = 1200
_DRAWING_MIN_HEIGHT = 800
_EXTREME_ASPECT_LOW = 0.35
_EXTREME_ASPECT_HIGH = 2.8
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_UNIT_PATTERN = re.compile(
    r"(㎡|m²|平方米|平米|米|m\b|km|公里|万|亿元|元|%|层|栋|套|个|人|床|间)",
    re.IGNORECASE,
)
_EXTERNAL_FACT_PATTERN = re.compile(r"(据|行业|研究|统计|报告显示|数据显示|文献)")
_PROBLEM_PATTERN = re.compile(r"(问题|病害|破损|老化|渗漏|开裂|隐患|不足|缺陷)")
_STRATEGY_PATTERN = re.compile(r"(策略|改造|整治|更新|提升|优化)")
_TARGET_PATTERN = re.compile(r"(层|区|栋|部位|入口|屋面|立面|平面|地下|地上|东侧|西侧|南侧|北侧)")
_BEFORE_AFTER_PATTERN = re.compile(r"(前后|对比|改造前|改造后|before|after)", re.IGNORECASE)
_GENERIC_CAPTION_PATTERN = re.compile(r"^(配图|示意图|图片|照片|效果图|素材)$")


def _tokenize(text: str) -> set[str]:
    return {
        token.strip().lower()
        for token in re.split(r"[\s，,、；;。.]+", text)
        if len(token.strip()) >= 2
    }


def _slide_text_blob(slide: SlideSpec) -> str:
    parts = [slide.title, slide.message, *slide.key_points]
    if slide.speaker_notes:
        parts.append(slide.speaker_notes)
    return " ".join(parts)


def _is_reference_asset(
    asset: Asset,
    documents_by_id: dict[UUID, SourceDocument],
) -> bool:
    metadata = asset.metadata or {}
    if metadata.get("is_reference") is True:
        return True
    purpose = document_purpose_from_metadata(metadata)
    if purpose.value in {"reference_case", "reference_style", "public_research"}:
        return True
    if "reference" in asset.tags:
        return True
    if asset.document_id is not None:
        document = documents_by_id.get(asset.document_id)
        if document is not None and is_reference_document(document.metadata):
            return True
    return False


def _text_supports_visual(slide: SlideSpec, description: str) -> bool:
    message_tokens = _tokenize(slide.message)
    description_tokens = _tokenize(description)
    if not message_tokens or not description_tokens:
        return True
    if message_tokens & description_tokens:
        return True
    for point in slide.key_points:
        if _tokenize(point) & description_tokens:
            return True
    return False


def _has_metric_without_unit(text: str) -> bool:
    for match in _NUMBER_PATTERN.finditer(text):
        start = max(0, match.start() - 8)
        end = min(len(text), match.end() + 8)
        window = text[start:end]
        if not _UNIT_PATTERN.search(window):
            return True
    return False


def run_slide_semantic_qa(
    presentation_id: UUID,
    slides: list[SlideSpec],
    *,
    project_id: UUID | None = None,
    brief: PresentationBrief | None = None,
    assets_by_id: dict[UUID, Asset] | None = None,
    documents_by_id: dict[UUID, SourceDocument] | None = None,
    renovation_issue_map: RenovationIssueMap | None = None,
    reference_style_profile: ReferenceStyleProfile | None = None,
    has_project_sources: bool = False,
) -> ArchitectureSlideSemanticQA:
    """Run deterministic per-slide semantic checks."""
    del reference_style_profile  # reserved for future style-fit heuristics

    assets_by_id = assets_by_id or {}
    documents_by_id = documents_by_id or {}
    renovation_mode = is_renovation_scenario(brief=brief) and renovation_issue_map is not None

    findings: list[SlideSemanticFinding] = []
    checked = 0

    for slide in slides:
        if slide.slide_type.value in _SKIPPABLE:
            continue
        checked += 1
        slide_text = _slide_text_blob(slide)

        bound_assets: list[Asset] = []
        for requirement in slide.visual_requirements:
            if requirement.type == VisualType.TEXT_ONLY:
                continue
            for asset_id in requirement.bound_asset_ids():
                asset = assets_by_id.get(asset_id)
                if asset is not None:
                    bound_assets.append(asset)

        for requirement in slide.visual_requirements:
            if requirement.type == VisualType.TEXT_ONLY or not requirement.required:
                continue

            asset_id = requirement.primary_asset_id
            asset = assets_by_id.get(asset_id) if asset_id is not None else None

            if asset is not None and _is_reference_asset(asset, documents_by_id):
                findings.append(
                    SlideSemanticFinding(
                        check_code=SlideSemanticCheckCode.REFERENCE_ASSET_USED_AS_PROJECT_ASSET,
                        slide_order=slide.order,
                        slide_id=slide.id,
                        severity="high",
                        title="参考素材被当作项目成果使用",
                        description=(
                            f"第 {slide.order + 1} 页绑定了参考案例/风格素材「{asset.filename}」，"
                            "可能误导为本项目实景或方案。"
                        ),
                        suggestion="替换为本项目图纸/照片，或在图注中明确标注为参考案例。",
                        evidence_refs=[str(asset.id)],
                    )
                )

            if (
                asset is not None
                and not _is_reference_asset(asset, documents_by_id)
                and has_project_sources
                and not slide.source_citations
            ):
                findings.append(
                    SlideSemanticFinding(
                        check_code=SlideSemanticCheckCode.PROJECT_ASSET_WITHOUT_SOURCE,
                        slide_order=slide.order,
                        slide_id=slide.id,
                        severity="medium",
                        title="项目素材缺少来源标注",
                        description=(
                            f"第 {slide.order + 1} 页使用了项目素材「{asset.filename}」，"
                            "但未关联引用来源。"
                        ),
                        suggestion="补充 chunk 引用或在图注中标明图纸/照片出处。",
                        evidence_refs=[str(asset.id)],
                    )
                )

            if requirement.type in _DRAWING_TYPES and asset is not None:
                if (
                    asset.width is not None
                    and asset.height is not None
                    and (asset.width < _DRAWING_MIN_WIDTH or asset.height < _DRAWING_MIN_HEIGHT)
                ):
                    findings.append(
                        SlideSemanticFinding(
                            check_code=SlideSemanticCheckCode.DRAWING_TOO_SMALL,
                            slide_order=slide.order,
                            slide_id=slide.id,
                            severity="medium",
                            title="主图图面占比可能不足",
                            description=(
                                f"第 {slide.order + 1} 页 {requirement.type.value} 素材"
                                f"「{asset.filename}」分辨率为 {asset.width}×{asset.height}，"
                                "投影时主图可能偏小。"
                            ),
                            suggestion="放大主图区域、拆分页面或替换更高分辨率图纸。",
                            evidence_refs=[str(asset.id)],
                        )
                    )
                ratio = asset.aspect_ratio
                if requirement.needs_crop or (
                    ratio is not None
                    and (ratio < _EXTREME_ASPECT_LOW or ratio > _EXTREME_ASPECT_HIGH)
                ):
                    findings.append(
                        SlideSemanticFinding(
                            check_code=SlideSemanticCheckCode.DRAWING_CROP_RISK,
                            slide_order=slide.order,
                            slide_id=slide.id,
                            severity="suggestion",
                            title="图纸存在裁切风险",
                            description=(
                                f"第 {slide.order + 1} 页图纸「{asset.filename if asset else '未命名'}」"
                                "宽高比极端或已标记需裁剪，关键标注可能被截断。"
                            ),
                            suggestion="检查图框完整性，必要时调整版式或重新导出图纸。",
                            evidence_refs=[str(asset.id)] if asset is not None else [],
                        )
                    )

            description = requirement.description.strip()
            if description and not _text_supports_visual(slide, description):
                findings.append(
                    SlideSemanticFinding(
                        check_code=SlideSemanticCheckCode.TEXT_NOT_EXPLAINING_VISUAL,
                        slide_order=slide.order,
                        slide_id=slide.id,
                        severity="medium",
                        title="文字未有效解释主图",
                        description=(
                            f"第 {slide.order + 1} 页核心文字与视觉需求「{description}」"
                            "关联较弱，图文可能脱节。"
                        ),
                        suggestion="在核心信息或要点中点明图中关键要素与结论关系。",
                    )
                )

            if asset is not None and (
                not description
                or _GENERIC_CAPTION_PATTERN.match(description)
                or len(description) < 4
            ):
                findings.append(
                    SlideSemanticFinding(
                        check_code=SlideSemanticCheckCode.VISUAL_WITHOUT_CAPTION,
                        slide_order=slide.order,
                        slide_id=slide.id,
                        severity="suggestion",
                        title="主图缺少有效图注",
                        description=(
                            f"第 {slide.order + 1} 页已绑定素材「{asset.filename}」，"
                            "但视觉说明过于笼统。"
                        ),
                        suggestion="补充图名、视角、楼层或拍摄位置等说明。",
                        evidence_refs=[str(asset.id)],
                    )
                )

        weighted_visuals = [
            requirement
            for requirement in slide.visual_requirements
            if requirement.required
            and requirement.type != VisualType.TEXT_ONLY
            and requirement.preferred_asset_ids
        ]
        if len(weighted_visuals) >= 3:
            findings.append(
                SlideSemanticFinding(
                    check_code=SlideSemanticCheckCode.TOO_MANY_EQUAL_WEIGHT_IMAGES,
                    slide_order=slide.order,
                    slide_id=slide.id,
                    severity="medium",
                    title="同页多图权重相当",
                    description=(
                        f"第 {slide.order + 1} 页包含 {len(weighted_visuals)} 个同级主图，"
                        "可能削弱单一结论的表达。"
                    ),
                    suggestion="明确主图与辅图层级，或拆分为前后页。",
                )
            )

        if _BEFORE_AFTER_PATTERN.search(slide_text):
            visual_count = sum(
                1
                for requirement in slide.visual_requirements
                if requirement.required and requirement.type != VisualType.TEXT_ONLY
            )
            if visual_count < 2:
                findings.append(
                    SlideSemanticFinding(
                        check_code=SlideSemanticCheckCode.BEFORE_AFTER_MISMATCH,
                        slide_order=slide.order,
                        slide_id=slide.id,
                        severity="medium",
                        title="前后对比信息不完整",
                        description=(
                            f"第 {slide.order + 1} 页提及前后/对比，但仅匹配到 {visual_count} 个视觉位。"
                        ),
                        suggestion="补充改造前与改造后成对图像，或使用对比版式。",
                    )
                )

        if renovation_mode and _PROBLEM_PATTERN.search(slide_text) and not slide.source_citations:
            findings.append(
                SlideSemanticFinding(
                    check_code=SlideSemanticCheckCode.ISSUE_WITHOUT_EVIDENCE,
                    slide_order=slide.order,
                    slide_id=slide.id,
                    severity="high",
                    title="问题判断缺少证据链",
                    description=(
                        f"第 {slide.order + 1} 页描述了现状/病害问题，"
                        "但未关联调研证据或引用来源。"
                    ),
                    suggestion="对照改造问题图谱补充现场照片、检测报告或图纸依据。",
                )
            )

        if renovation_mode and _STRATEGY_PATTERN.search(slide_text):
            if not _TARGET_PATTERN.search(slide_text):
                findings.append(
                    SlideSemanticFinding(
                        check_code=SlideSemanticCheckCode.STRATEGY_WITHOUT_TARGET,
                        slide_order=slide.order,
                        slide_id=slide.id,
                        severity="medium",
                        title="策略缺少明确对象",
                        description=(
                            f"第 {slide.order + 1} 页提出改造/策略方向，"
                            "但未指明具体空间、部位或楼栋。"
                        ),
                        suggestion="补充策略作用范围，如楼层、区域或构造部位。",
                    )
                )

        if _NUMBER_PATTERN.search(slide.message) and _has_metric_without_unit(slide.message):
            findings.append(
                SlideSemanticFinding(
                    check_code=SlideSemanticCheckCode.METRIC_WITHOUT_UNIT,
                    slide_order=slide.order,
                    slide_id=slide.id,
                    severity="medium",
                    title="指标缺少单位",
                    description=f"第 {slide.order + 1} 页核心信息含数值，但未明确单位。",
                    suggestion="为面积、高度、造价等指标补充标准单位。",
                )
            )

        if _EXTERNAL_FACT_PATTERN.search(slide_text) and not slide.source_citations:
            findings.append(
                SlideSemanticFinding(
                    check_code=SlideSemanticCheckCode.EXTERNAL_FACT_WITHOUT_CITATION,
                    slide_order=slide.order,
                    slide_id=slide.id,
                    severity="high",
                    title="外部事实缺少引用",
                    description=(
                        f"第 {slide.order + 1} 页引用行业/研究/统计表述，"
                        "但未标注出处。"
                    ),
                    suggestion="补充报告、标准或公开数据来源。",
                )
            )

    return ArchitectureSlideSemanticQA(
        presentation_id=presentation_id,
        project_id=project_id,
        findings=findings,
        checked_slide_count=checked,
    )
