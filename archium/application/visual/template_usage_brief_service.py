"""Build and write TemplateUsageBrief artifacts after Template Induction."""

from __future__ import annotations

import json
from pathlib import Path

from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplateSlotRole,
)
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.template_induction import TemplateInductionResult
from archium.domain.visual.template_usage_brief import TemplateUsageBrief

BRIEF_MARKDOWN_NAME = "TemplateUsageBrief.md"
BRIEF_JSON_NAME = "template_usage_brief.json"

_DEFAULT_FORBIDDEN = [
    "图纸不得使用 cover / crop；图纸 fit 必须为 contain，禁止裁切比例",
    "参考案例图不得冒充本项目证据或现场照片",
    "禁止连续同构卡片轰炸（多页重复同一卡片网格而无叙事推进）",
]

_DEFAULT_MOTION = [
    "静态汇报页：不依赖入场动画或网页动效表达重点",
    "以阅读顺序、字号层级与留白表达重点，而非动效",
]

_SECTION_TITLES = (
    "品牌特征",
    "标题行为",
    "字体层级",
    "页边距",
    "内容密度",
    "图片处理",
    "图纸处理",
    "页码位置",
    "重复装饰",
    "禁用模式",
)


class TemplateUsageBriefService:
    """Deterministic Theme/usage contract from ArchitecturalTemplate (+ optional DS)."""

    def build_brief(
        self,
        template: ArchitecturalTemplate,
        *,
        design_system: DesignSystem | None = None,
        induction: TemplateInductionResult | None = None,
    ) -> TemplateUsageBrief:
        evidence: list[str] = []
        if design_system is None:
            evidence.append("design_system=missing")
        else:
            evidence.append(f"design_system={design_system.name}")

        source_name = Path(template.source_pptx_path).name if template.source_pptx_path else ""
        palette = self._palette(template, design_system, evidence)
        fonts = self._fonts(template, design_system, evidence)
        margins = self._page_margins(template, design_system, evidence)
        title_behavior = self._title_behavior(template.layouts, evidence)
        typography = self._typography_hierarchy(design_system, fonts, evidence)
        density = self._content_density(template.layouts, evidence)
        image_treatment = self._image_treatment(template, design_system, evidence)
        drawing_treatment = self._drawing_treatment(template, design_system, evidence)
        page_number = self._page_number_position(template, design_system, evidence)
        decorations = self._repeated_decorations(template.layouts, evidence)
        forbidden = list(_DEFAULT_FORBIDDEN)
        if induction is not None:
            for warning in induction.warnings:
                text = str(warning).strip()
                if text and text not in forbidden:
                    forbidden.append(f"induction warning: {text}")
            evidence.append(f"induction_id={induction.id}")

        brand_traits = self._brand_traits(template, palette, fonts, evidence)

        return TemplateUsageBrief(
            template_id=str(template.id),
            template_name=template.name,
            source_filename=source_name,
            brand_traits=brand_traits,
            title_behavior=title_behavior,
            typography_hierarchy=typography,
            page_margins=margins,
            content_density=density,
            image_treatment=image_treatment,
            drawing_treatment=drawing_treatment,
            page_number_position=page_number,
            repeated_decorations=decorations,
            forbidden_patterns=forbidden,
            palette=palette,
            fonts=fonts,
            motion_principles=list(_DEFAULT_MOTION),
            evidence=evidence,
        )

    def render_markdown(self, brief: TemplateUsageBrief) -> str:
        lines: list[str] = [
            f"# Template Usage Brief — {brief.template_name}",
            "",
            f"- template_id: `{brief.template_id}`",
        ]
        if brief.source_filename:
            lines.append(f"- source: `{brief.source_filename}`")
        lines.append("")

        lines.extend(["## 品牌特征", ""])
        lines.extend(self._bullets(brief.brand_traits) or ["- （未归纳到明确品牌特征）"])
        lines.append("")

        lines.extend(["## 标题行为", "", brief.title_behavior or "（未检测到标题槽）", ""])

        lines.extend(["## 字体层级", ""])
        lines.extend(self._bullets(brief.typography_hierarchy) or ["- （无 typography tokens）"])
        lines.append("")

        lines.extend(["## 页边距", ""])
        if brief.page_margins:
            for key in ("width", "height", "top", "right", "bottom", "left"):
                if key in brief.page_margins:
                    lines.append(f"- {key}: {brief.page_margins[key]}")
            for key, value in brief.page_margins.items():
                if key not in {"width", "height", "top", "right", "bottom", "left"}:
                    lines.append(f"- {key}: {value}")
        else:
            lines.append("- （未推导）")
        lines.append("")

        lines.extend(["## 内容密度", "", brief.content_density or "（未聚合）", ""])

        lines.extend(["## 图片处理", "", brief.image_treatment or "（未推导）", ""])

        lines.extend(["## 图纸处理", "", brief.drawing_treatment or "（未推导）", ""])

        lines.extend(["## 页码位置", "", brief.page_number_position or "（未检测到页码）", ""])

        lines.extend(["## 重复装饰", ""])
        lines.extend(self._bullets(brief.repeated_decorations) or ["- （无明显重复装饰）"])
        lines.append("")

        lines.extend(["## 禁用模式", ""])
        lines.extend(self._bullets(brief.forbidden_patterns))
        lines.append("")

        if brief.palette:
            lines.extend(["## 调色板", ""])
            lines.extend(self._bullets(brief.palette))
            lines.append("")
        if brief.fonts:
            lines.extend(["## 字体", ""])
            lines.extend(self._bullets(brief.fonts))
            lines.append("")
        if brief.motion_principles:
            lines.extend(["## 动效原则", ""])
            lines.extend(self._bullets(brief.motion_principles))
            lines.append("")
        if brief.evidence:
            lines.extend(["## 派生依据", ""])
            lines.extend(self._bullets(brief.evidence))
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def write_artifacts(
        self,
        workspace: Path,
        brief: TemplateUsageBrief,
    ) -> dict[str, Path]:
        workspace.mkdir(parents=True, exist_ok=True)
        md_path = workspace / BRIEF_MARKDOWN_NAME
        json_path = workspace / BRIEF_JSON_NAME
        md_path.write_text(self.render_markdown(brief), encoding="utf-8")
        json_path.write_text(
            json.dumps(brief.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"template_usage_brief_md": md_path, "template_usage_brief_json": json_path}

    def write_for_template(
        self,
        workspace: Path,
        template: ArchitecturalTemplate,
        *,
        design_system: DesignSystem | None = None,
        induction: TemplateInductionResult | None = None,
    ) -> tuple[TemplateUsageBrief, dict[str, Path]]:
        brief = self.build_brief(
            template, design_system=design_system, induction=induction
        )
        paths = self.write_artifacts(workspace, brief)
        return brief, paths

    @staticmethod
    def section_titles() -> tuple[str, ...]:
        return _SECTION_TITLES

    @staticmethod
    def _bullets(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items if str(item).strip()]

    def _palette(
        self,
        template: ArchitecturalTemplate,
        design_system: DesignSystem | None,
        evidence: list[str],
    ) -> list[str]:
        if design_system is not None:
            colors = design_system.colors
            palette = [
                f"background={colors.background}",
                f"primary={colors.primary}",
                f"accent={colors.accent}",
                f"primary_text={colors.primary_text}",
                f"secondary={colors.secondary}",
            ]
            evidence.append("palette=design_system.colors")
            return palette
        colors = [c for c in template.colors if c]
        evidence.append(f"palette=template.colors count={len(colors)}")
        return colors[:16]

    def _fonts(
        self,
        template: ArchitecturalTemplate,
        design_system: DesignSystem | None,
        evidence: list[str],
    ) -> list[str]:
        if design_system is not None:
            ty = design_system.typography
            families = sorted(
                {
                    ty.title.font_family,
                    ty.body.font_family,
                    ty.caption.font_family,
                    ty.display.font_family,
                }
            )
            evidence.append("fonts=design_system.typography")
            return families
        from_layouts = sorted(
            {f for layout in template.layouts for f in layout.extracted_fonts if f}
        )
        from_assets = [f.family for f in template.fonts if f.family]
        fonts = list(dict.fromkeys([*from_assets, *from_layouts]))
        evidence.append(f"fonts=template count={len(fonts)}")
        return fonts

    def _page_margins(
        self,
        template: ArchitecturalTemplate,
        design_system: DesignSystem | None,
        evidence: list[str],
    ) -> dict[str, float]:
        if design_system is not None:
            page = design_system.page
            evidence.append("page_margins=design_system.page")
            return {
                "width": page.width,
                "height": page.height,
                "top": page.margin_top,
                "right": page.margin_right,
                "bottom": page.margin_bottom,
                "left": page.margin_left,
            }

        layout = template.layouts[0] if template.layouts else None
        width = layout.page_width if layout else 10.0
        height = layout.page_height if layout else 5.625
        if layout and layout.slots:
            xs = [s.x for s in layout.slots]
            ys = [s.y for s in layout.slots]
            rights = [s.x + s.width for s in layout.slots]
            bottoms = [s.y + s.height for s in layout.slots]
            margins = {
                "width": width,
                "height": height,
                "top": round(min(ys), 3),
                "left": round(min(xs), 3),
                "right": round(max(0.0, width - max(rights)), 3),
                "bottom": round(max(0.0, height - max(bottoms)), 3),
            }
            evidence.append("page_margins=heuristic_from_representative_slots")
            return margins

        evidence.append("page_margins=default_16x9")
        return {
            "width": width,
            "height": height,
            "top": 0.45,
            "right": 0.7,
            "bottom": 0.45,
            "left": 0.7,
        }

    def _title_behavior(
        self,
        layouts: list[ArchitecturalTemplateLayout],
        evidence: list[str],
    ) -> str:
        titles = [
            slot
            for layout in layouts
            for slot in layout.slots
            if slot.role == TemplateSlotRole.TITLE
        ]
        if not titles:
            evidence.append("title_behavior=no_title_slots")
            return "未检测到 TITLE 槽；标题行为需人工确认或后续补槽。"
        avg_y = sum(s.y for s in titles) / len(titles)
        avg_h = sum(s.height for s in titles) / len(titles)
        position = "顶栏" if avg_y <= 1.0 else ("中部" if avg_y <= 2.5 else "偏下")
        lines_hint = "偏单行结论式" if avg_h <= 0.85 else "允许多行标题区"
        evidence.append(f"title_slots={len(titles)}")
        return (
            f"标题槽约 {len(titles)} 处，几何偏{position} "
            f"(avg y={avg_y:.2f}in, h={avg_h:.2f}in)；{lines_hint}。"
        )

    def _typography_hierarchy(
        self,
        design_system: DesignSystem | None,
        fonts: list[str],
        evidence: list[str],
    ) -> list[str]:
        if design_system is not None:
            ty = design_system.typography
            evidence.append("typography=design_system")
            return [
                f"display {ty.display.font_size:g}pt / {ty.display.font_family}",
                f"title {ty.title.font_size:g}pt / {ty.title.font_family}",
                f"subtitle {ty.subtitle.font_size:g}pt / {ty.subtitle.font_family}",
                f"heading {ty.heading.font_size:g}pt / {ty.heading.font_family}",
                f"body {ty.body.font_size:g}pt / {ty.body.font_family}",
                f"caption {ty.caption.font_size:g}pt / {ty.caption.font_family}",
            ]
        if fonts:
            evidence.append("typography=fonts_only_no_pt")
            return [f"available families: {', '.join(fonts)}"]
        evidence.append("typography=unavailable")
        return []

    def _content_density(
        self,
        layouts: list[ArchitecturalTemplateLayout],
        evidence: list[str],
    ) -> str:
        if not layouts:
            evidence.append("density=no_layouts")
            return "无 layout；密度未定义。"
        lows = [layout.density_range[0] for layout in layouts]
        highs = [layout.density_range[1] for layout in layouts]
        lo, hi = min(lows), max(highs)
        mid = (sum(lows) + sum(highs)) / (2 * len(layouts))
        label = "疏" if mid < 0.35 else ("中" if mid < 0.55 else "密")
        evidence.append(f"density_range_aggregate=({lo:.2f},{hi:.2f})")
        return f"聚合 density_range [{lo:.2f}, {hi:.2f}]，整体偏{label}（中位约 {mid:.2f}）。"

    def _image_treatment(
        self,
        template: ArchitecturalTemplate,
        design_system: DesignSystem | None,
        evidence: list[str],
    ) -> str:
        photo_slots = sum(
            1
            for layout in template.layouts
            for slot in layout.slots
            if slot.role
            in {TemplateSlotRole.HERO_IMAGE, TemplateSlotRole.SUPPORTING_IMAGE}
        )
        parts: list[str] = []
        if design_system is not None:
            style = design_system.image_style
            parts.append(
                f"DesignSystem image_style: fit={style.default_fit.value}, "
                f"photo_treatment={style.photo_treatment.value}"
            )
            evidence.append("image_treatment=design_system.image_style")
        else:
            parts.append("无 DesignSystem：照片槽按模板几何放置，避免随意 cover。")
            evidence.append("image_treatment=template_slots_only")
        parts.append(f"检测到 photo/hero 槽 {photo_slots} 个。")
        return " ".join(parts)

    def _drawing_treatment(
        self,
        template: ArchitecturalTemplate,
        design_system: DesignSystem | None,
        evidence: list[str],
    ) -> str:
        drawing_slots = [
            slot
            for layout in template.layouts
            for slot in layout.slots
            if slot.role == TemplateSlotRole.DRAWING
        ]
        hard = (
            "Archium 硬规则：图纸必须 contain（完整可见、保持比例），"
            "禁止 cover / crop；不得为填满槽位裁切图纸。"
        )
        extras: list[str] = []
        if design_system is not None:
            style = design_system.image_style
            extras.append(
                f"DS drawing_preserve_aspect_ratio={style.drawing_preserve_aspect_ratio}, "
                f"drawing_background={style.drawing_background}"
            )
        if drawing_slots:
            crops = sorted({s.crop_policy for s in drawing_slots})
            extras.append(
                f"drawing 槽 {len(drawing_slots)} 个；crop_policy={','.join(crops)}"
            )
        evidence.append("drawing_treatment=hard_rule_contain")
        return hard + ((" " + " ".join(extras)) if extras else "")

    def _page_number_position(
        self,
        template: ArchitecturalTemplate,
        design_system: DesignSystem | None,
        evidence: list[str],
    ) -> str:
        if design_system is not None:
            footer = design_system.footer_style
            evidence.append("page_number=design_system.footer_style")
            if not footer.enabled or not footer.show_page_number:
                return "DesignSystem footer 未启用页码。"
            return (
                f"页码位于页脚带（footer height≈{footer.height:g}in，"
                f"font_token={footer.font_token}）。"
            )

        # Heuristic: bottom-band slots that look like chrome.
        candidates = []
        for layout in template.layouts:
            for slot in layout.slots:
                if slot.role == TemplateSlotRole.SOURCE:
                    candidates.append(slot)
                elif slot.role == TemplateSlotRole.DECORATION and slot.y >= layout.page_height * 0.85:
                    candidates.append(slot)
                elif "page" in (slot.label or "").lower() or "页码" in (slot.label or ""):
                    candidates.append(slot)
        if not candidates:
            evidence.append("page_number=undetected")
            return "未从槽位几何推断到明确页码位置；默认页脚右侧/居中需人工确认。"
        avg_y = sum(s.y for s in candidates) / len(candidates)
        evidence.append(f"page_number_slots={len(candidates)}")
        return f"推测页码/页脚带约在 y≈{avg_y:.2f}in（底部装饰/来源槽启发式）。"

    def _repeated_decorations(
        self,
        layouts: list[ArchitecturalTemplateLayout],
        evidence: list[str],
    ) -> list[str]:
        decor = [
            slot
            for layout in layouts
            for slot in layout.slots
            if slot.role == TemplateSlotRole.DECORATION
        ]
        evidence.append(f"decoration_slots={len(decor)}")
        if not decor:
            return []
        # Group by rough geometry bucket for "repeated" signal.
        buckets: dict[str, int] = {}
        for slot in decor:
            key = f"y~{round(slot.y, 1)} h~{round(slot.height, 2)}"
            buckets[key] = buckets.get(key, 0) + 1
        items = [
            f"装饰槽 {count}× @ {key}"
            for key, count in sorted(buckets.items(), key=lambda kv: -kv[1])
        ]
        return items[:12]

    def _brand_traits(
        self,
        template: ArchitecturalTemplate,
        palette: list[str],
        fonts: list[str],
        evidence: list[str],
    ) -> list[str]:
        traits: list[str] = []
        if template.name:
            traits.append(f"模板名：{template.name}")
        page_types = sorted({layout.page_type.value for layout in template.layouts})
        if page_types:
            traits.append(f"版式类型覆盖：{', '.join(page_types[:8])}")
        if fonts:
            traits.append(f"主字体线索：{', '.join(fonts[:4])}")
        if palette:
            traits.append(f"色板线索数：{len(palette)}")
        drawing_layouts = sum(1 for layout in template.layouts if layout.supports_drawing)
        if drawing_layouts:
            traits.append(f"含图纸焦点版式 {drawing_layouts} 个")
        evidence.append(f"brand_traits={len(traits)}")
        return traits
