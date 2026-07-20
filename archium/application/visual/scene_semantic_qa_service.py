"""Scene-level semantic QA against RenderScene (WP H §11.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.domain.slide_semantic_qa import ArchitectureSlideSemanticQA, SlideSemanticFinding
from archium.domain.visual.render_scene import DrawingNode, ImageNode, RenderScene, TextNode
from archium.domain.visual.scene_qa import SceneSemanticCheckCode, is_project_presentation_role
from archium.infrastructure.renderers.renderer_conformance import assert_renderer_conformance

_ANALYZER_VERSION = "scene-qa-1.0.0"
_MIN_READABLE_FONT_PT = 10.0
# Rough characters that fit in a text box at ~font_size pt (page inches → approx).
_CHARS_PER_INCH_AT_12PT = 12.0


def run_scene_semantic_qa(
    presentation_id: UUID,
    scenes: list[RenderScene],
    *,
    project_id: UUID | None = None,
    pptx_paths_by_slide: dict[UUID, Path] | None = None,
    slide_orders: dict[UUID, int] | None = None,
) -> ArchitectureSlideSemanticQA:
    """Run RenderScene semantic checks and return aggregated findings."""
    findings: list[SlideSemanticFinding] = []
    orders = slide_orders or {}
    pptx_map = pptx_paths_by_slide or {}

    for scene in scenes:
        order = orders.get(scene.slide_id, 0)
        findings.extend(_check_scene(scene, slide_order=order, pptx_path=pptx_map.get(scene.slide_id)))

    return ArchitectureSlideSemanticQA(
        presentation_id=presentation_id,
        project_id=project_id,
        findings=findings,
        checked_slide_count=len(scenes),
        analyzer_version=_ANALYZER_VERSION,
    )


def _check_scene(
    scene: RenderScene,
    *,
    slide_order: int,
    pptx_path: Path | None,
) -> list[SlideSemanticFinding]:
    findings: list[SlideSemanticFinding] = []
    findings.extend(_check_drawing_cover(scene, slide_order=slide_order))
    findings.extend(_check_asset_provenance(scene, slide_order=slide_order))
    findings.extend(_check_unresolved_assets(scene, slide_order=slide_order))
    findings.extend(_check_font_size(scene, slide_order=slide_order))
    findings.extend(_check_text_overflow(scene, slide_order=slide_order))
    findings.extend(_check_caption_missing(scene, slide_order=slide_order))
    findings.extend(_check_font_fallback(scene, slide_order=slide_order))
    findings.extend(_check_scene_pptx_mismatch(scene, slide_order=slide_order, pptx_path=pptx_path))
    return findings


def _finding(
    *,
    check_code: str,
    slide_order: int,
    slide_id: UUID,
    severity: str,
    title: str,
    description: str,
    suggestion: str | None = None,
    evidence_refs: list[str] | None = None,
) -> SlideSemanticFinding:
    return SlideSemanticFinding(
        check_code=check_code,
        slide_order=slide_order,
        slide_id=slide_id,
        severity=severity,
        title=title,
        description=description,
        suggestion=suggestion,
        evidence_refs=list(evidence_refs or []),
    )


def _check_drawing_cover(scene: RenderScene, *, slide_order: int) -> list[SlideSemanticFinding]:
    findings: list[SlideSemanticFinding] = []
    for warning in scene.warnings:
        if warning.startswith("DRAWING_COVER_MODE_FORBIDDEN:"):
            node_id = warning.split(":", 1)[1]
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="high",
                    title="图纸禁止 cover 适配",
                    description=f"图纸节点 `{node_id}` 尝试使用 cover，已强制改为 contain。",
                    suggestion="图纸应保持等比完整显示，勿使用 cover。",
                    evidence_refs=[node_id],
                )
            )
    for node in scene.nodes:
        if isinstance(node, DrawingNode) and node.fit_mode not in {"contain", "safe_crop"}:
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="high",
                    title="图纸禁止 cover 适配",
                    description=f"图纸节点 `{node.id}` 的 fit_mode=`{node.fit_mode}` 非法。",
                    suggestion="将图纸 fit_mode 设为 contain 或 safe_crop。",
                    evidence_refs=[node.id],
                )
            )
    return findings


def _check_asset_provenance(scene: RenderScene, *, slide_order: int) -> list[SlideSemanticFinding]:
    findings: list[SlideSemanticFinding] = []
    for node in scene.nodes:
        if not isinstance(node, ImageNode):
            continue
        if not is_project_presentation_role(node.semantic_role):
            continue
        if node.asset_origin == "ai_generated":
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.AI_IMAGE_PRESENTED_AS_REAL_PROJECT,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="critical",
                    title="AI 生成图被当作真实项目成果",
                    description=(
                        f"节点 `{node.id}`（role={node.semantic_role}）来源为 AI 生成，"
                        "但被呈现为项目成果。"
                    ),
                    suggestion="改为参考案例标注，或替换为真实项目素材。",
                    evidence_refs=[node.id],
                )
            )
        elif node.asset_origin == "stock_image":
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.STOCK_IMAGE_PRESENTED_AS_PROJECT,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="high",
                    title="库存图被当作项目成果",
                    description=(
                        f"节点 `{node.id}`（role={node.semantic_role}）来源为库存图，"
                        "但被呈现为项目成果。"
                    ),
                    suggestion="标注为参考/示意，或替换为项目实景/图纸。",
                    evidence_refs=[node.id],
                )
            )
    return findings


def _check_unresolved_assets(scene: RenderScene, *, slide_order: int) -> list[SlideSemanticFinding]:
    findings: list[SlideSemanticFinding] = []
    for node in scene.nodes:
        if not isinstance(node, (ImageNode, DrawingNode)):
            continue
        if node.asset_unresolved or not node.asset_path:
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.IMAGE_NOT_RENDERED,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="high",
                    title="图片节点未渲染",
                    description=f"节点 `{node.id}` 素材未解析或路径为空，导出时将缺失图面。",
                    suggestion="重新绑定有效素材路径。",
                    evidence_refs=[node.id],
                )
            )
    return findings


def _check_font_size(scene: RenderScene, *, slide_order: int) -> list[SlideSemanticFinding]:
    findings: list[SlideSemanticFinding] = []
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        floor = max(node.minimum_font_size, _MIN_READABLE_FONT_PT)
        if node.font_size + 1e-6 < floor:
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.FONT_TOO_SMALL,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="medium",
                    title="Scene 字号过小",
                    description=(
                        f"文本节点 `{node.id}` 字号 {node.font_size:.1f}pt "
                        f"低于可读下限 {floor:.1f}pt。"
                    ),
                    suggestion="增大字号、缩短文案或放大文本框。",
                    evidence_refs=[node.id],
                )
            )
    return findings


def _check_text_overflow(scene: RenderScene, *, slide_order: int) -> list[SlideSemanticFinding]:
    findings: list[SlideSemanticFinding] = []
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        if node.overflow_policy != "error":
            continue
        text = (node.text or "").strip()
        if not text:
            continue
        scale = max(node.font_size, 1.0) / 12.0
        capacity = max(1.0, node.width * _CHARS_PER_INCH_AT_12PT / scale) * max(
            1.0, node.height / (node.line_height * node.font_size / 72.0)
        )
        if len(text) > capacity * 1.25:
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.TEXT_OVERFLOW,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="medium",
                    title="Scene 文本可能溢出",
                    description=(
                        f"文本节点 `{node.id}` 在 overflow_policy=error 下字符量可能超出框体。"
                    ),
                    suggestion="缩短文案、缩小字号策略改为 shrink，或扩大文本框。",
                    evidence_refs=[node.id],
                )
            )
    return findings


def _check_caption_missing(scene: RenderScene, *, slide_order: int) -> list[SlideSemanticFinding]:
    findings: list[SlideSemanticFinding] = []
    caption_ids = {
        node.id
        for node in scene.nodes
        if isinstance(node, TextNode) and node.semantic_role in {"caption", "source", "citation"}
    }
    for node in scene.nodes:
        if not isinstance(node, ImageNode):
            continue
        if node.semantic_role not in {"project_photo", "hero_visual"} and "hero" not in node.id:
            if node.semantic_role != "project_photo":
                continue
        has_caption = bool(node.caption_node_id) or bool(caption_ids)
        if not has_caption:
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.CAPTION_MISSING,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="suggestion",
                    title="主图缺少图注节点",
                    description=f"主图节点 `{node.id}` 未关联 caption，也未检测到页面图注文本。",
                    suggestion="补充图注或绑定 caption_node_id。",
                    evidence_refs=[node.id],
                )
            )
    return findings


def _check_font_fallback(scene: RenderScene, *, slide_order: int) -> list[SlideSemanticFinding]:
    findings: list[SlideSemanticFinding] = []
    known = {asset.family for asset in scene.font_assets if asset.family}
    if not known:
        return findings
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        if node.font_family and node.font_family not in known:
            findings.append(
                _finding(
                    check_code=SceneSemanticCheckCode.FONT_FALLBACK_CHANGED_LAYOUT,
                    slide_order=slide_order,
                    slide_id=scene.slide_id,
                    severity="medium",
                    title="字体回退可能改变版式",
                    description=(
                        f"文本节点 `{node.id}` 使用字体 `{node.font_family}`，"
                        "不在 Scene font_assets 中，渲染端可能回退字体导致重排。"
                    ),
                    suggestion="将字体加入 font_assets，或改用设计系统已声明字体。",
                    evidence_refs=[node.id],
                )
            )
    return findings


def _check_scene_pptx_mismatch(
    scene: RenderScene,
    *,
    slide_order: int,
    pptx_path: Path | None,
) -> list[SlideSemanticFinding]:
    if pptx_path is None or not pptx_path.is_file():
        return []
    report = assert_renderer_conformance(scene, pptx_path=pptx_path)
    if report.passed:
        return []
    return [
        _finding(
            check_code=SceneSemanticCheckCode.SCENE_PPTX_NODE_MISMATCH,
            slide_order=slide_order,
            slide_id=scene.slide_id,
            severity="high",
            title="Scene 与 PPTX 节点不一致",
            description="；".join(report.issues[:4]),
            suggestion="检查 PPTX 导出是否丢失文本或图片节点。",
            evidence_refs=report.issues[:6],
        )
    ]
