"""Layered deterministic QA for Studio SceneChangeProposal workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from archium.application.visual.post_render_qa_service import run_post_render_qa
from archium.application.visual.scene_proposal_qa import findings_to_quality_issues
from archium.application.visual.scene_semantic_qa_service import (
    run_scene_semantic_qa,
)
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.domain.visual.page_quality import (
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityIssueSource,
)
from archium.domain.visual.quality_issue_catalog import default_severity_for_auto_code
from archium.domain.visual.render_scene import (
    BaseRenderNode,
    DrawingNode,
    ImageNode,
    RenderScene,
)
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.validation import (
    LAYOUT_ELEMENT_OUTSIDE_PAGE,
    LAYOUT_ELEMENT_OVERLAP,
    LAYOUT_UNRESOLVED_ASSET_PATH,
)
from archium.infrastructure.layout.geometry import Rect

_OVERLAP_TOLERANCE = 0.01
_RENDER_PREVIEW_FAILED = "RENDER.PREVIEW_FAILED"
_RENDER_PREVIEW_MISSING = "RENDER.PREVIEW_MISSING"

ProposalQALayer = str


@dataclass(frozen=True)
class ProposalSceneQAResult:
    """Aggregated QA for one RenderScene used in proposal review."""

    issues: tuple[QualityIssue, ...]
    layers: dict[ProposalQALayer, tuple[QualityIssue, ...]]
    preview_path: Path | None = None
    preview_render_success: bool = True


def run_proposal_scene_qa(
    presentation_id: UUID,
    scene: RenderScene,
    *,
    slide_order: int = 0,
    studio_scene: StudioSceneService | None = None,
    include_post_render: bool = True,
) -> ProposalSceneQAResult:
    """Run deterministic scene QA layers for proposal create/accept gates."""
    semantic_report = run_scene_semantic_qa(
        presentation_id,
        [scene],
        slide_orders={scene.slide_id: slide_order},
    )
    semantic_issues = findings_to_quality_issues(semantic_report.findings)

    geometry_issues = _run_geometry_qa(scene)
    asset_issues = _run_asset_qa(scene)
    drawing_issues = _run_drawing_qa(scene)

    render_issues: list[QualityIssue] = []
    preview_path: Path | None = None
    preview_render_success = True
    if studio_scene is not None:
        try:
            preview_path = studio_scene.render_scene_preview(presentation_id, scene)
            if not preview_path.is_file():
                preview_render_success = False
                render_issues.append(
                    _quality_issue(
                        code=_RENDER_PREVIEW_MISSING,
                        message="Scene 预览 PNG 未能生成。",
                        severity=IssueSeverity.BLOCKER,
                        category=IssueCategory.LAYOUT_VISUAL,
                        evidence=[str(preview_path)],
                    )
                )
        except Exception as exc:
            preview_render_success = False
            render_issues.append(
                _quality_issue(
                    code=_RENDER_PREVIEW_FAILED,
                    message=f"Scene 预览渲染失败：{exc}",
                    severity=IssueSeverity.BLOCKER,
                    category=IssueCategory.LAYOUT_VISUAL,
                    evidence=[scene.id.hex],
                )
            )

    post_render_issues: list[QualityIssue] = []
    if include_post_render and preview_render_success and preview_path is not None:
        post_report = run_post_render_qa(
            presentation_id,
            [(scene.slide_id, preview_path)],
            scenes_by_slide={scene.slide_id: scene},
            slide_orders={scene.slide_id: slide_order},
        )
        post_render_issues = findings_to_quality_issues(post_report.findings)

    layers: dict[ProposalQALayer, tuple[QualityIssue, ...]] = {
        "semantic": tuple(semantic_issues),
        "geometry": tuple(geometry_issues),
        "asset": tuple(asset_issues),
        "drawing": tuple(drawing_issues),
        "render": tuple(render_issues),
        "post_render": tuple(post_render_issues),
    }
    merged = _dedupe_issues(
        [
            *semantic_issues,
            *geometry_issues,
            *asset_issues,
            *drawing_issues,
            *render_issues,
            *post_render_issues,
        ]
    )
    return ProposalSceneQAResult(
        issues=tuple(merged),
        layers=layers,
        preview_path=preview_path,
        preview_render_success=preview_render_success,
    )


def _run_geometry_qa(scene: RenderScene) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    page = Rect(0, 0, scene.page_width, scene.page_height)
    node_rects: list[tuple[BaseRenderNode, Rect]] = []

    for node in scene.nodes:
        if node.width <= 0 or node.height <= 0:
            continue
        rect = Rect(node.x, node.y, node.width, node.height)
        node_rects.append((node, rect))
        if (
            rect.x < page.x - 1e-6
            or rect.y < page.y - 1e-6
            or rect.right > page.right + 1e-6
            or rect.bottom > page.bottom + 1e-6
        ):
            issues.append(
                _quality_issue(
                    code=LAYOUT_ELEMENT_OUTSIDE_PAGE,
                    message=f"节点 `{node.id}` 超出页面边界。",
                    severity=IssueSeverity.BLOCKER,
                    category=IssueCategory.LAYOUT_VISUAL,
                    evidence=[node.id],
                )
            )

    for index, (left, left_rect) in enumerate(node_rects):
        for right, right_rect in node_rects[index + 1 :]:
            if left.id == right.id:
                continue
            if left_rect.overlaps(right_rect, tolerance=_OVERLAP_TOLERANCE):
                issues.append(
                    _quality_issue(
                        code=LAYOUT_ELEMENT_OVERLAP,
                        message=f"节点 `{left.id}` 与 `{right.id}` 发生重叠。",
                        severity=IssueSeverity.BLOCKER,
                        category=IssueCategory.LAYOUT_VISUAL,
                        evidence=sorted([left.id, right.id]),
                    )
                )
    return issues


def _run_asset_qa(scene: RenderScene) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    manifest_ids = {
        ref.asset_id
        for ref in scene.asset_manifest
        if ref.asset_id is not None
    }
    for node in scene.nodes:
        if not isinstance(node, (ImageNode, DrawingNode)):
            continue
        if node.asset_unresolved or not (node.storage_uri or node.asset_path):
            issues.append(
                _quality_issue(
                    code=LAYOUT_UNRESOLVED_ASSET_PATH,
                    message=f"节点 `{node.id}` 素材 URI 未解析或为空。",
                    severity=IssueSeverity.BLOCKER,
                    category=IssueCategory.DELIVERY_EDITABILITY,
                    evidence=[node.id],
                )
            )
            continue
        if node.asset_id is not None and node.asset_id not in manifest_ids:
            issues.append(
                _quality_issue(
                    code="ASSET.MANIFEST_MISSING",
                    message=f"节点 `{node.id}` 的素材未写入 Scene asset_manifest。",
                    severity=IssueSeverity.MAJOR,
                    category=IssueCategory.DELIVERY_EDITABILITY,
                    evidence=[node.id, str(node.asset_id)],
                )
            )
    return issues


def _run_drawing_qa(scene: RenderScene) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for node in scene.nodes:
        if not isinstance(node, DrawingNode):
            continue
        if node.fit_mode not in {"contain", "safe_crop"}:
            issues.append(
                _quality_issue(
                    code=SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN,
                    message=f"图纸节点 `{node.id}` 的 fit_mode=`{node.fit_mode}` 非法。",
                    severity=IssueSeverity.BLOCKER,
                    category=IssueCategory.ARCHITECTURAL,
                    evidence=[node.id],
                )
            )
        if node.crop_allowed and node.fit_mode == "contain":
            issues.append(
                _quality_issue(
                    code="DRAWING.CROP_ALLOWED_ON_CONTAIN",
                    message=f"图纸节点 `{node.id}` 在 contain 模式下不应允许裁切。",
                    severity=IssueSeverity.MAJOR,
                    category=IssueCategory.ARCHITECTURAL,
                    evidence=[node.id],
                )
            )
    return issues


def _quality_issue(
    *,
    code: str,
    message: str,
    severity: IssueSeverity | None = None,
    category: IssueCategory,
    evidence: list[str] | None = None,
) -> QualityIssue:
    resolved = severity or default_severity_for_auto_code(code)
    return QualityIssue(
        code=code,
        severity=resolved,
        category=category,
        message=message,
        evidence=list(evidence or []),
        source=QualityIssueSource.AUTO,
    )


def _dedupe_issues(issues: list[QualityIssue]) -> list[QualityIssue]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    ordered: list[QualityIssue] = []
    for issue in issues:
        key = (issue.code, tuple(sorted(issue.evidence)))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(issue)
    return ordered


def summarize_layer_counts(layers: dict[str, tuple[QualityIssue, ...]]) -> dict[str, int]:
    """Return blocker+major counts per QA layer for UI summaries."""
    counts: dict[str, int] = {}
    for layer, issues in layers.items():
        counts[layer] = sum(
            1
            for issue in issues
            if issue.severity in {IssueSeverity.BLOCKER, IssueSeverity.MAJOR}
        )
    return counts
