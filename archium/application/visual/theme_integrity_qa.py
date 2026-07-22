"""Theme integrity QA — protect drawings, evidence, charts, and citations."""

from __future__ import annotations

import colorsys
import re

from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import ImageFit, PhotoTreatment
from archium.domain.visual.page_quality import (
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityIssueSource,
)
from archium.domain.visual.render_scene import DrawingNode, ImageNode, RenderScene, TextNode

THEME_DRAWING_COLOR_INTEGRITY = "THEME.DRAWING_COLOR_INTEGRITY"
THEME_EVIDENCE_PHOTO_TREATMENT = "THEME.EVIDENCE_PHOTO_TREATMENT_POLICY"
THEME_CHART_SEMANTIC_COLOR = "THEME.CHART_SEMANTIC_COLOR_PROTECTION"
THEME_CITATION_CONTRAST = "THEME.CITATION_CONTRAST"


def run_theme_integrity_qa(
    *,
    base: DesignSystem,
    proposed: DesignSystem,
    sample_scenes: list[RenderScene] | None = None,
) -> list[QualityIssue]:
    """Gate deck theme accepts that would damage evidence / drawing semantics."""
    issues: list[QualityIssue] = []
    issues.extend(_check_drawing_integrity(base, proposed))
    issues.extend(_check_photo_treatment(proposed))
    issues.extend(_check_chart_palette(base, proposed))
    if sample_scenes:
        for scene in sample_scenes:
            issues.extend(_check_citation_contrast(scene, proposed))
            issues.extend(_check_drawing_nodes_untinted(scene, proposed))
    return _dedupe(issues)


def _check_drawing_integrity(base: DesignSystem, proposed: DesignSystem) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if proposed.image_style.default_fit != ImageFit.CONTAIN:
        issues.append(
            QualityIssue(
                code=THEME_DRAWING_COLOR_INTEGRITY,
                severity=IssueSeverity.BLOCKER,
                category=IssueCategory.ARCHITECTURAL,
                message="主题不得把默认图片 fit 设为非 contain（图纸会 cover/crop）。",
                source=QualityIssueSource.AUTO,
                suggested_fix="保持 image_style.default_fit=contain。",
            )
        )
    if not proposed.image_style.drawing_preserve_aspect_ratio:
        issues.append(
            QualityIssue(
                code=THEME_DRAWING_COLOR_INTEGRITY,
                severity=IssueSeverity.BLOCKER,
                category=IssueCategory.ARCHITECTURAL,
                message="主题关闭了图纸等比保留，存在重绘/变形风险。",
                source=QualityIssueSource.AUTO,
            )
        )
    # Recoloring drawing paper away from near-white is treated as integrity risk.
    if _is_strongly_tinted(proposed.image_style.drawing_background) and (
        proposed.image_style.drawing_background.upper()
        != (base.image_style.drawing_background or "").upper()
    ):
        issues.append(
            QualityIssue(
                code=THEME_DRAWING_COLOR_INTEGRITY,
                severity=IssueSeverity.BLOCKER,
                category=IssueCategory.ARCHITECTURAL,
                message="主题不得对建筑图纸纸面重新着色（drawing_background 强染色）。",
                evidence=[proposed.image_style.drawing_background],
                source=QualityIssueSource.AUTO,
                suggested_fix="保持图纸纸面近白/中性，勿套品牌主色。",
            )
        )
    return issues


def _check_photo_treatment(proposed: DesignSystem) -> list[QualityIssue]:
    treatment = proposed.image_style.photo_treatment
    if treatment == PhotoTreatment.HISTORICAL:
        return [
            QualityIssue(
                code=THEME_EVIDENCE_PHOTO_TREATMENT,
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.IMAGE_TEXT,
                message="全稿 historical 照片处理可能使现场证据失真；证据页应保持纪实观感。",
                source=QualityIssueSource.AUTO,
                suggested_fix="证据照片使用 none / subtle_unify；勿对项目证据套复古滤镜。",
            )
        ]
    if treatment == PhotoTreatment.DOCUMENT_SCAN:
        return [
            QualityIssue(
                code=THEME_EVIDENCE_PHOTO_TREATMENT,
                severity=IssueSeverity.MINOR,
                category=IssueCategory.IMAGE_TEXT,
                message="document_scan 处理可能压掉现场照片色彩；请确认不用于关键证据页。",
                source=QualityIssueSource.AUTO,
            )
        ]
    return []


def _check_chart_palette(base: DesignSystem, proposed: DesignSystem) -> list[QualityIssue]:
    base_palette = list(base.chart_style.palette_tokens)
    proposed_palette = list(proposed.chart_style.palette_tokens)
    if not proposed_palette:
        return [
            QualityIssue(
                code=THEME_CHART_SEMANTIC_COLOR,
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.CONTENT,
                message="主题清空了图表语义色板，数据系列颜色可能丢失语义。",
                source=QualityIssueSource.AUTO,
            )
        ]
    # If every series collapses to a single brand token, semantic protection fails.
    if len(set(proposed_palette)) == 1 and proposed_palette[0] in {"primary", "accent"}:
        return [
            QualityIssue(
                code=THEME_CHART_SEMANTIC_COLOR,
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.CONTENT,
                message="图表色板被压成单一品牌色，可能破坏系列对比语义。",
                evidence=proposed_palette,
                source=QualityIssueSource.AUTO,
                suggested_fix="保留多色语义 palette_tokens，勿全部替换为 primary/accent。",
            )
        ]
    if base_palette and proposed_palette == ["primary"] * len(proposed_palette):
        return [
            QualityIssue(
                code=THEME_CHART_SEMANTIC_COLOR,
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.CONTENT,
                message="主题强制图表套主色，存在数据语义丢失风险。",
                source=QualityIssueSource.AUTO,
            )
        ]
    return []


def _check_citation_contrast(scene: RenderScene, proposed: DesignSystem) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    try:
        bg = proposed.colors.resolve("background")
        muted = proposed.colors.resolve("muted_text")
    except KeyError:
        return issues
    ratio = _contrast_ratio(bg, muted)
    if ratio < 3.0:
        issues.append(
            QualityIssue(
                code=THEME_CITATION_CONTRAST,
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.LAYOUT_VISUAL,
                message=f"来源/脚注色与背景对比不足（约 {ratio:.1f}:1），来源标记可能不可读。",
                evidence=[f"slide={scene.slide_id}", f"bg={bg}", f"muted={muted}"],
                source=QualityIssueSource.AUTO,
                suggested_fix="提高 muted_text / source 对比度，或避免过浅背景。",
            )
        )
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        if node.semantic_role not in {"citation", "source", "footnote"}:
            continue
        color = node.color
        if node.color_token:
            try:
                color = proposed.colors.resolve(node.color_token)
            except KeyError:
                pass
        node_ratio = _contrast_ratio(bg, color)
        if node_ratio < 3.0:
            issues.append(
                QualityIssue(
                    code=THEME_CITATION_CONTRAST,
                    severity=IssueSeverity.MAJOR,
                    category=IssueCategory.LAYOUT_VISUAL,
                    message=f"来源节点 `{node.id}` 对比不足（约 {node_ratio:.1f}:1）。",
                    evidence=[node.id, color, bg],
                    source=QualityIssueSource.AUTO,
                )
            )
    return issues


def _check_drawing_nodes_untinted(
    scene: RenderScene,
    proposed: DesignSystem,
) -> list[QualityIssue]:
    """Ensure drawing nodes stay contain and are not treated as brand-tinted photos."""
    issues: list[QualityIssue] = []
    for node in scene.nodes:
        if not isinstance(node, DrawingNode):
            continue
        fit = getattr(node, "fit_mode", None) or getattr(node, "fit", None)
        if fit and str(fit) != "contain":
            issues.append(
                QualityIssue(
                    code=THEME_DRAWING_COLOR_INTEGRITY,
                    severity=IssueSeverity.BLOCKER,
                    category=IssueCategory.ARCHITECTURAL,
                    message=f"图纸节点 `{node.id}` fit≠contain，主题预览不得接受。",
                    evidence=[node.id, str(fit)],
                    source=QualityIssueSource.AUTO,
                )
            )
        if isinstance(node, ImageNode):  # pragma: no cover - DrawingNode path
            pass
    # Evidence photos must not inherit historical treatment as identity
    if proposed.image_style.photo_treatment == PhotoTreatment.HISTORICAL:
        for node in scene.nodes:
            if not isinstance(node, ImageNode):
                continue
            if node.semantic_role in {"project_photo", "evidence", "site_photo"} or (
                node.asset_origin == "project_upload"
                and "reference" not in (node.semantic_role or "")
            ):
                issues.append(
                    QualityIssue(
                        code=THEME_EVIDENCE_PHOTO_TREATMENT,
                        severity=IssueSeverity.MAJOR,
                        category=IssueCategory.IMAGE_TEXT,
                        message=f"证据/项目照片节点 `{node.id}` 不应被全稿 historical 处理染色。",
                        evidence=[node.id, node.semantic_role],
                        source=QualityIssueSource.AUTO,
                    )
                )
                break
    return issues


def _is_strongly_tinted(hex_color: str) -> bool:
    rgb = _parse_hex(hex_color)
    if rgb is None:
        return False
    r, g, b = [c / 255.0 for c in rgb]
    _h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return s > 0.25 and v < 0.95


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    a = _relative_luminance(hex_a)
    b = _relative_luminance(hex_b)
    if a is None or b is None:
        return 21.0
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(hex_color: str) -> float | None:
    rgb = _parse_hex(hex_color)
    if rgb is None:
        return None

    def _channel(value: int) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _parse_hex(value: str) -> tuple[int, int, int] | None:
    cleaned = value.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{3}|[0-9a-fA-F]{6}", cleaned):
        return None
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)


def _dedupe(issues: list[QualityIssue]) -> list[QualityIssue]:
    seen: set[tuple[str, str]] = set()
    result: list[QualityIssue] = []
    for issue in issues:
        key = (issue.code, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result
