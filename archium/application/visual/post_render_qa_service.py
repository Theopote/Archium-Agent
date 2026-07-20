"""Deck-level post-render screenshot QA (WP H §11.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.domain.slide_semantic_qa import ArchitectureSlideSemanticQA, SlideSemanticFinding
from archium.domain.visual.render_scene import DrawingNode, ImageNode, RenderScene
from archium.domain.visual.scene_qa import PostRenderCheckCode
from archium.infrastructure.vision.screenshot_qa import (
    ScreenshotCheck,
    analyze_slide_screenshot,
    average_hash,
    compare_png_pptx_screenshots,
    hash_distance,
    load_image,
)

_ANALYZER_VERSION = "post-render-qa-1.0.0"
_SEVERE_STRETCH_RATIO = 1.45


def run_post_render_qa(
    presentation_id: UUID,
    screenshots: list[tuple[UUID, Path]],
    *,
    project_id: UUID | None = None,
    scenes_by_slide: dict[UUID, RenderScene] | None = None,
    pptx_screenshots: dict[UUID, Path] | None = None,
    slide_orders: dict[UUID, int] | None = None,
) -> ArchitectureSlideSemanticQA:
    """Analyze page screenshots; soft-skips missing files."""
    findings: list[SlideSemanticFinding] = []
    orders = slide_orders or {}
    scenes = scenes_by_slide or {}
    pptx_shots = pptx_screenshots or {}
    loaded: list[tuple[UUID, object, Path]] = []

    for slide_id, path in screenshots:
        image = load_image(path)
        if image is None:
            continue
        order = orders.get(slide_id, 0)
        for check in analyze_slide_screenshot(image):
            if check.passed:
                continue
            findings.append(_from_check(check, slide_id=slide_id, slide_order=order))
        scene = scenes.get(slide_id)
        if scene is not None:
            findings.extend(
                _check_severe_stretch(scene, image, slide_id=slide_id, slide_order=order)
            )
        pptx_path = pptx_shots.get(slide_id)
        if pptx_path is not None:
            pptx_image = load_image(pptx_path)
            if pptx_image is not None:
                diff = compare_png_pptx_screenshots(image, pptx_image)
                if not diff.passed:
                    findings.append(_from_check(diff, slide_id=slide_id, slide_order=order))
        loaded.append((slide_id, image, path))

    findings.extend(_check_duplicates(loaded, orders=orders))

    return ArchitectureSlideSemanticQA(
        presentation_id=presentation_id,
        project_id=project_id,
        findings=findings,
        checked_slide_count=len(loaded),
        analyzer_version=_ANALYZER_VERSION,
    )


def _from_check(
    check: ScreenshotCheck,
    *,
    slide_id: UUID,
    slide_order: int,
) -> SlideSemanticFinding:
    return SlideSemanticFinding(
        check_code=check.check_code,
        slide_order=slide_order,
        slide_id=slide_id,
        severity=check.severity,
        title=check.title,
        description=check.description,
        suggestion=check.suggestion,
        evidence_refs=[f"{key}={value}" for key, value in check.evidence.items()],
    )


def _check_severe_stretch(
    scene: RenderScene,
    image: object,
    *,
    slide_id: UUID,
    slide_order: int,
) -> list[SlideSemanticFinding]:
    del image  # reserved for region-level crop analysis
    findings: list[SlideSemanticFinding] = []
    for node in scene.nodes:
        if not isinstance(node, (ImageNode, DrawingNode)):
            continue
        if node.width <= 0 or node.height <= 0:
            continue
        # Without embedded source dimensions, use fit_mode cover on drawings as stretch risk.
        if isinstance(node, DrawingNode) and node.fit_mode != "contain":
            findings.append(
                SlideSemanticFinding(
                    check_code=PostRenderCheckCode.SEVERE_STRETCH,
                    slide_order=slide_order,
                    slide_id=slide_id,
                    severity="medium",
                    title="渲染页图片严重拉伸",
                    description=f"图纸节点 `{node.id}` fit_mode=`{node.fit_mode}`，存在拉伸风险。",
                    suggestion="图纸使用 contain 并保持宽高比。",
                    evidence_refs=[node.id],
                )
            )
        if isinstance(node, ImageNode) and node.fit_mode == "cover":
            box_ratio = node.width / node.height
            if box_ratio > _SEVERE_STRETCH_RATIO or box_ratio < 1 / _SEVERE_STRETCH_RATIO:
                findings.append(
                    SlideSemanticFinding(
                        check_code=PostRenderCheckCode.SEVERE_STRETCH,
                        slide_order=slide_order,
                        slide_id=slide_id,
                        severity="suggestion",
                        title="渲染页图片严重拉伸",
                        description=f"图片节点 `{node.id}` 框体宽高比极端且 fit=cover。",
                        suggestion="改用 contain 或调整框体比例。",
                        evidence_refs=[node.id],
                    )
                )
    return findings


def _check_duplicates(
    loaded: list[tuple[UUID, object, Path]],
    *,
    orders: dict[UUID, int],
) -> list[SlideSemanticFinding]:
    if len(loaded) < 2:
        return []
    hashes = [(slide_id, average_hash(image)) for slide_id, image, _path in loaded]  # type: ignore[arg-type]
    findings: list[SlideSemanticFinding] = []
    identical = True
    for index, (slide_id, digest) in enumerate(hashes):
        for other_id, other_digest in hashes[index + 1 :]:
            distance = hash_distance(digest, other_digest)
            if distance > 0:
                identical = False
            if distance <= 6 and slide_id != other_id:
                findings.append(
                    SlideSemanticFinding(
                        check_code=PostRenderCheckCode.DUPLICATE_PAGE,
                        slide_order=orders.get(slide_id, 0),
                        slide_id=slide_id,
                        severity="medium",
                        title="渲染页与其他页过于相似",
                        description=(
                            f"页面与 slide `{other_id}` 的 aHash 距离为 {distance}，疑似重复页。"
                        ),
                        suggestion="检查是否误用同一版式导出。",
                        evidence_refs=[str(slide_id), str(other_id), f"distance={distance}"],
                    )
                )
    if identical and len(hashes) >= 2:
        first_id = hashes[0][0]
        findings.append(
            SlideSemanticFinding(
                check_code=PostRenderCheckCode.ALL_PAGES_IDENTICAL,
                slide_order=orders.get(first_id, 0),
                slide_id=first_id,
                severity="high",
                title="全部渲染页几乎相同",
                description=f"共 {len(hashes)} 页截图 aHash 完全一致。",
                suggestion="检查截图生成是否始终输出同一页。",
                evidence_refs=[str(slide_id) for slide_id, _ in hashes],
            )
        )
    return findings
