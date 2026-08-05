"""Apply text↔background contrast guard on RenderScene (readability)."""

from __future__ import annotations

from archium.application.visual.color_contrast import (
    contrast_ratio,
    ensure_contrast,
    min_ratio_for_role,
)
from archium.domain.visual.render_scene import (
    RenderScene,
    TextNode,
    TextRun,
    effective_run_style,
    set_text_node_runs,
)

WARNING_TAG = "text_contrast:enforced"


def apply_text_background_contrast_to_scene(scene: object) -> object:
    """Force TextNode colors to meet role-based contrast vs page background.

    Safe to call multiple times: only patches nodes that still fail.
    """
    if not isinstance(scene, RenderScene):
        return scene

    bg = getattr(scene.background, "color", None) or "#FFFFFF"
    nodes: list[object] = []
    fixed = 0
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            nodes.append(node)
            continue
        # Skip fully transparent / decorative empty labels.
        if float(getattr(node, "opacity", 1.0)) < 0.08:
            nodes.append(node)
            continue
        min_ratio = min_ratio_for_role(
            node.semantic_role,
            font_size=float(node.font_size or 14),
            font_weight=int(node.font_weight or 400),
        )
        # Opacity reduces effective contrast roughly; raise the bar slightly when faded.
        opacity = max(0.15, float(node.opacity or 1.0))
        effective_min = min_ratio / max(opacity, 0.35) if opacity < 0.95 else min_ratio
        effective_min = min(effective_min, 7.0)

        original = node.color or "#000000"
        ratio = contrast_ratio(original, bg)
        if ratio >= effective_min - 1e-6:
            nodes.append(node)
            continue

        safe = ensure_contrast(original, bg, min_ratio=effective_min)
        updated = node.model_copy(update={"color": safe, "color_token": ""})
        fixed += 1
        if node.runs:
            runs = []
            for run in node.runs:
                style = effective_run_style(node, run)
                run_fg = style["color"] or original
                run_safe = ensure_contrast(run_fg, bg, min_ratio=effective_min)
                runs.append(
                    TextRun(
                        text=run.text,
                        font_family=run.font_family,
                        font_family_cjk=run.font_family_cjk,
                        font_family_latin=run.font_family_latin,
                        font_size=run.font_size,
                        font_weight=run.font_weight,
                        font_style=run.font_style,
                        color=run_safe,
                        color_token="",
                    )
                )
            set_text_node_runs(updated, runs)
        nodes.append(updated)

    warnings = list(scene.warnings)
    if WARNING_TAG not in warnings:
        warnings.append(WARNING_TAG)
    if fixed:
        warnings.append(f"text_contrast:fixed={fixed}")
    return scene.model_copy(update={"nodes": nodes, "warnings": warnings})


def scene_text_contrast_failures(scene: RenderScene) -> list[dict[str, object]]:
    """List text nodes that still fail contrast (for Critic evidence)."""
    bg = getattr(scene.background, "color", None) or "#FFFFFF"
    failures: list[dict[str, object]] = []
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        if float(getattr(node, "opacity", 1.0)) < 0.08:
            continue
        min_ratio = min_ratio_for_role(
            node.semantic_role,
            font_size=float(node.font_size or 14),
            font_weight=int(node.font_weight or 400),
        )
        ratio = contrast_ratio(node.color, bg)
        if ratio < min_ratio:
            failures.append(
                {
                    "node_id": node.id,
                    "semantic_role": node.semantic_role,
                    "color": node.color,
                    "background": bg,
                    "ratio": round(ratio, 2),
                    "min_ratio": min_ratio,
                }
            )
    return failures


__all__ = [
    "WARNING_TAG",
    "apply_text_background_contrast_to_scene",
    "scene_text_contrast_failures",
]
