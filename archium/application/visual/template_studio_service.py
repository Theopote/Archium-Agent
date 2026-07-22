"""Template Studio application service."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy.orm import Session

from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.config.settings import Settings, get_settings
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.slide import SlideSpec
from archium.domain.slide_recovery import HybridRenderScene, SlideRecoveryPageKind
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateSlot,
    TemplateSlotRole,
    TemplateStatus,
)
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.design_system import DesignSystem, TextStyleToken
from archium.domain.visual.enums import (
    DesignSystemSource,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import FontAsset
from archium.exceptions import WorkflowError
from archium.infrastructure.database.visual_repositories import (
    ArchitecturalTemplateRepository,
    DesignSystemRepository,
)
from archium.infrastructure.renderers.canvas_renderer import CanvasRenderer
from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)
from archium.infrastructure.template.pptx_structure_extractor import PptxStructureExtractor
from archium.infrastructure.vision.analyzer import check_dominant_colors

_SLOT_TO_LAYOUT_ROLE: dict[TemplateSlotRole, LayoutElementRole] = {
    TemplateSlotRole.TITLE: LayoutElementRole.TITLE,
    TemplateSlotRole.SUBTITLE: LayoutElementRole.SUBTITLE,
    TemplateSlotRole.BODY: LayoutElementRole.BODY_TEXT,
    TemplateSlotRole.HERO_IMAGE: LayoutElementRole.HERO_VISUAL,
    TemplateSlotRole.SUPPORTING_IMAGE: LayoutElementRole.SUPPORTING_VISUAL,
    TemplateSlotRole.DRAWING: LayoutElementRole.HERO_VISUAL,
    TemplateSlotRole.METRIC: LayoutElementRole.METRIC,
    TemplateSlotRole.CAPTION: LayoutElementRole.CAPTION,
    TemplateSlotRole.SOURCE: LayoutElementRole.SOURCE,
    TemplateSlotRole.CHART: LayoutElementRole.SUPPORTING_VISUAL,
    TemplateSlotRole.TABLE: LayoutElementRole.BODY_TEXT,
    TemplateSlotRole.DECORATION: LayoutElementRole.DECORATION,
}

_PAGE_TYPE_TO_FAMILY: dict[TemplatePageType, LayoutFamily] = {
    TemplatePageType.COVER: LayoutFamily.HERO,
    TemplatePageType.SECTION: LayoutFamily.HERO,
    TemplatePageType.AGENDA: LayoutFamily.TEXTUAL_ARGUMENT,
    TemplatePageType.TEXT_ARGUMENT: LayoutFamily.TEXTUAL_ARGUMENT,
    TemplatePageType.DRAWING_FOCUS: LayoutFamily.DRAWING_FOCUS,
    TemplatePageType.PHOTO_GRID: LayoutFamily.EVIDENCE_BOARD,
    TemplatePageType.BEFORE_AFTER: LayoutFamily.COMPARATIVE_MATRIX,
    TemplatePageType.CASE_COMPARISON: LayoutFamily.COMPARATIVE_MATRIX,
    TemplatePageType.METRIC: LayoutFamily.METRIC_DASHBOARD,
    TemplatePageType.TIMELINE: LayoutFamily.PROCESS_NARRATIVE,
    TemplatePageType.PROCESS: LayoutFamily.PROCESS_NARRATIVE,
    TemplatePageType.CLOSING: LayoutFamily.HERO,
    TemplatePageType.UNKNOWN: LayoutFamily.TEXTUAL_ARGUMENT,
}

_TEST_FILL_TEXT: dict[TemplateSlotRole, str] = {
    TemplateSlotRole.TITLE: "测试标题：院区空间策略",
    TemplateSlotRole.SUBTITLE: "测试副标题：结构清晰 · 证据充分",
    TemplateSlotRole.BODY: (
        "这是 Template Studio 的测试填充正文。用于验证槽位可替换文案，"
        "并确认模板结构、字体与颜色可在生成预览中复现。"
    ),
    TemplateSlotRole.CAPTION: "图注：测试内容填充",
    TemplateSlotRole.SOURCE: "来源：模板测试数据",
    TemplateSlotRole.METRIC: "12.5 万㎡",
}


@dataclass(frozen=True)
class TemplateImportResult:
    template: ArchitecturalTemplate
    screenshot_count: int
    screenshot_tools_available: bool
    warnings: list[str]


@dataclass(frozen=True)
class TemplateFillPreviewResult:
    template_id: UUID
    layout_id: str
    preview_path: Path
    layout_plan: LayoutPlan


@dataclass(frozen=True)
class RecoveryTemplateSaveResult:
    template: ArchitecturalTemplate
    layout_id: str
    preview_path: Path


class TemplateStudioService:
    """Import, analyze, annotate, fill, and publish architectural templates."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        extractor: PptxStructureExtractor | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._extractor = extractor or PptxStructureExtractor()
        self._templates = ArchitecturalTemplateRepository(session)
        self._designs = DesignSystemRepository(session)

    def workspace_root(self, template_id: UUID) -> Path:
        path = self._settings.output_path / "template-studio" / str(template_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_templates(self, *, project_id: UUID | None = None) -> list[ArchitecturalTemplate]:
        if project_id is None:
            return self._templates.list_all()
        return self._templates.list_by_project(project_id)

    def get_template(self, template_id: UUID) -> ArchitecturalTemplate | None:
        return self._templates.get(template_id)

    def import_pptx(
        self,
        pptx_path: Path | str,
        *,
        name: str | None = None,
        project_id: UUID | None = None,
    ) -> TemplateImportResult:
        source = Path(pptx_path)
        if not source.is_file():
            raise WorkflowError(f"PPTX 文件不存在：{source}")
        if source.suffix.lower() not in {".pptx", ".pptm"}:
            raise WorkflowError("仅支持 .pptx / .pptm 模板文件。")

        template_id = uuid4()
        workspace = self.workspace_root(template_id)
        stored_pptx = workspace / "source.pptx"
        shutil.copy2(source, stored_pptx)

        extraction = self._extractor.extract(stored_pptx)
        if extraction.metadata.encrypted_or_unreadable:
            raise WorkflowError(
                "无法读取 PPTX（可能加密或损坏）："
                + (extraction.metadata.notes or "未知错误")
            )

        screenshots_dir = workspace / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        tools_ok = screenshot_tools_available()
        warnings = list(extraction.warnings)
        screenshot_paths: dict[int, Path] = {}
        pngs = export_pptx_slide_pngs(stored_pptx, screenshots_dir) if tools_ok else []
        if tools_ok and not pngs:
            warnings.append("截图工具可用但未能生成页面预览，将继续使用结构分析。")
        if not tools_ok:
            warnings.append(
                "未检测到 LibreOffice + pdftoppm，页面截图跳过；仍可进行槽位标注。"
            )
        for index, png in enumerate(pngs):
            screenshot_paths[index] = png

        # Augment colors from screenshots when available.
        colors = list(extraction.colors)
        for png in pngs[:6]:
            try:
                with Image.open(png) as image:
                    check = check_dominant_colors(image)
                for item in cast(
                    list[object], check.evidence.get("dominant_colors", [])
                ):
                    if isinstance(item, dict) and isinstance(item.get("hex"), str):
                        colors.append(str(item["hex"]))
            except Exception:
                continue
        colors = list(dict.fromkeys(colors))[:16]

        layouts = self._extractor.to_layouts(extraction, screenshot_paths=screenshot_paths)
        design = self._build_imported_design_system(
            name=name or source.stem,
            fonts=extraction.fonts,
            colors=colors,
            source_reference=str(stored_pptx),
        )
        design = self._designs.save(design)

        template = ArchitecturalTemplate(
            id=template_id,
            name=name or source.stem,
            source_pptx_path=str(stored_pptx),
            project_id=project_id,
            design_system_id=design.id,
            fonts=[FontAsset(family=font) for font in extraction.fonts],
            colors=colors,
            layouts=layouts,
            source_master_metadata=extraction.metadata,
            status=TemplateStatus.DRAFT,
            workspace_dir=str(workspace),
            analysis_notes=warnings,
        )
        saved = self._templates.save(template)
        self._write_manifest(saved)
        return TemplateImportResult(
            template=saved,
            screenshot_count=len(pngs),
            screenshot_tools_available=tools_ok,
            warnings=warnings,
        )

    def create_from_recovery_reference(
        self,
        *,
        project_id: UUID,
        hybrid: HybridRenderScene,
        source_page_id: str,
        source_preview_path: Path | None = None,
        name: str | None = None,
    ) -> RecoveryTemplateSaveResult:
        template_id = uuid4()
        workspace = self.workspace_root(template_id)
        screenshots_dir = workspace / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        preview_path = screenshots_dir / "recovery_page_01.png"
        if source_preview_path is not None and source_preview_path.is_file():
            preview_path = screenshots_dir / f"source_preview{source_preview_path.suffix.lower()}"
            shutil.copy2(source_preview_path, preview_path)
        else:
            CanvasRenderer().render_preview(hybrid.scene, preview_path)

        design = self._build_recovery_design_system(
            name=name or source_page_id,
            scene=hybrid.scene,
            source_reference=str(preview_path),
        )
        design = self._designs.save(design)
        layout = self._layout_from_recovery_reference(
            source_page_id=source_page_id,
            hybrid=hybrid,
            preview_path=preview_path,
        )

        template = ArchitecturalTemplate(
            id=template_id,
            name=name or f"Recovery Reference · {source_page_id}",
            source_pptx_path="",
            project_id=project_id,
            design_system_id=design.id,
            fonts=list(hybrid.scene.font_assets),
            colors=self._scene_colors(hybrid.scene),
            layouts=[layout],
            status=TemplateStatus.DRAFT,
            workspace_dir=str(workspace),
            analysis_notes=[
                "created_from_slide_recovery",
                f"page_kind={hybrid.page_kind.value}",
                f"fidelity={hybrid.reconstruction_fidelity.value}",
            ],
        )
        saved = self._save(template)
        return RecoveryTemplateSaveResult(
            template=saved,
            layout_id=layout.id,
            preview_path=preview_path,
        )

    def update_page_type(
        self,
        template_id: UUID,
        layout_id: str,
        page_type: TemplatePageType,
    ) -> ArchitecturalTemplate:
        template = self._require_template(template_id)
        layouts: list[ArchitecturalTemplateLayout] = []
        found = False
        for layout in template.layouts:
            if layout.id == layout_id:
                layouts.append(
                    layout.model_copy(
                        update={
                            "page_type": page_type,
                            "suitable_slide_types": [page_type.value],
                            "classification_confidence": 1.0,
                            "classification_notes": "manual override",
                        }
                    )
                )
                found = True
            else:
                layouts.append(layout)
        if not found:
            raise WorkflowError(f"未找到模板页面：{layout_id}")
        return self._save(template.model_copy(update={"layouts": layouts}))

    def update_layout_slots(
        self,
        template_id: UUID,
        layout_id: str,
        slots: list[TemplateSlot],
    ) -> ArchitecturalTemplate:
        template = self._require_template(template_id)
        layouts: list[ArchitecturalTemplateLayout] = []
        found = False
        for layout in template.layouts:
            if layout.id == layout_id:
                layouts.append(layout.model_copy(update={"slots": list(slots)}))
                found = True
            else:
                layouts.append(layout)
        if not found:
            raise WorkflowError(f"未找到模板页面：{layout_id}")
        return self._save(template.model_copy(update={"layouts": layouts}))

    def upsert_slot(
        self,
        template_id: UUID,
        layout_id: str,
        slot: TemplateSlot,
    ) -> ArchitecturalTemplate:
        template = self._require_template(template_id)
        layout = template.layout_by_id(layout_id)
        if layout is None:
            raise WorkflowError(f"未找到模板页面：{layout_id}")
        slots = [item for item in layout.slots if item.id != slot.id]
        slots.append(slot)
        return self.update_layout_slots(template_id, layout_id, slots)

    def delete_slot(
        self,
        template_id: UUID,
        layout_id: str,
        slot_id: str,
    ) -> ArchitecturalTemplate:
        template = self._require_template(template_id)
        layout = template.layout_by_id(layout_id)
        if layout is None:
            raise WorkflowError(f"未找到模板页面：{layout_id}")
        slots = [item for item in layout.slots if item.id != slot_id]
        return self.update_layout_slots(template_id, layout_id, slots)

    def fill_test_content_preview(
        self,
        template_id: UUID,
        layout_id: str,
    ) -> TemplateFillPreviewResult:
        template = self._require_template(template_id)
        layout = template.layout_by_id(layout_id)
        if layout is None:
            raise WorkflowError(f"未找到模板页面：{layout_id}")
        design = None
        if template.design_system_id is not None:
            design = self._designs.get(template.design_system_id)
        if design is None:
            design = default_presentation_design_system()

        slide_id = uuid4()
        plan = self._layout_plan_from_template_page(
            layout=layout,
            design_system_id=design.id,
            slide_id=slide_id,
        )
        slide = SlideSpec(
            id=slide_id,
            presentation_id=uuid4(),
            title=next(
                (
                    slot.label or _TEST_FILL_TEXT[TemplateSlotRole.TITLE]
                    for slot in layout.slots
                    if slot.role == TemplateSlotRole.TITLE
                ),
                "模板测试页",
            ),
            slide_type=SlideType.CONTENT,
            order=layout.page_index,
            chapter_id="template-test",
            message="Template Studio 测试内容填充。",
        )
        # Template fill preview uses DesignSystem only (no project ArtDirection /
        # ReferenceStyle in this path). Project Studio compile path applies overlays.
        scene = RenderSceneCompiler().compile(
            slide=slide,
            layout_plan=plan,
            design_system=design,
            presentation_id=slide.presentation_id,
        )
        workspace = Path(template.workspace_dir or self.workspace_root(template.id))
        preview_dir = workspace / "fill-previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / f"{layout.id}.png"
        CanvasRenderer().render_preview(scene, preview_path)
        return TemplateFillPreviewResult(
            template_id=template.id,
            layout_id=layout.id,
            preview_path=preview_path,
            layout_plan=plan,
        )

    def publish(self, template_id: UUID) -> ArchitecturalTemplate:
        template = self._require_template(template_id)
        if not template.layouts:
            raise WorkflowError("模板没有页面，无法发布。")
        if not any(layout.slots for layout in template.layouts):
            raise WorkflowError("至少需要一个页面完成槽位标注后才能发布。")
        reference_style_id = template.reference_style_profile_id
        if reference_style_id is None and template.project_id is not None:
            reference_style_id = self._current_reference_style_id(template.project_id)
        return self._save(
            template.model_copy(
                update={
                    "status": TemplateStatus.PUBLISHED,
                    "version": template.version + 1,
                    "reference_style_profile_id": reference_style_id,
                }
            )
        )

    def _current_reference_style_id(self, project_id: UUID) -> UUID | None:
        from archium.infrastructure.database.models import ProjectORM

        orm = self._session.get(ProjectORM, project_id)
        if orm is None:
            return None
        return orm.current_reference_style_profile_id

    def _layout_plan_from_template_page(
        self,
        *,
        layout: ArchitecturalTemplateLayout,
        design_system_id: UUID,
        slide_id: UUID,
    ) -> LayoutPlan:
        family = _PAGE_TYPE_TO_FAMILY.get(layout.page_type, LayoutFamily.TEXTUAL_ARGUMENT)
        elements: list[LayoutElement] = []
        reading_order: list[str] = []
        hero_id: str | None = None
        for index, slot in enumerate(layout.slots):
            role = _SLOT_TO_LAYOUT_ROLE.get(slot.role, LayoutElementRole.BODY_TEXT)
            content_type = LayoutContentType.TEXT
            text_content = _TEST_FILL_TEXT.get(slot.role)
            if slot.role in {
                TemplateSlotRole.HERO_IMAGE,
                TemplateSlotRole.SUPPORTING_IMAGE,
                TemplateSlotRole.DRAWING,
                TemplateSlotRole.CHART,
            }:
                content_type = (
                    LayoutContentType.DRAWING
                    if slot.role == TemplateSlotRole.DRAWING
                    else LayoutContentType.IMAGE
                )
                text_content = None
            elif slot.role == TemplateSlotRole.TABLE:
                content_type = LayoutContentType.TABLE
            elif slot.role == TemplateSlotRole.METRIC:
                content_type = LayoutContentType.METRIC
            elif slot.role == TemplateSlotRole.DECORATION:
                content_type = LayoutContentType.SHAPE
                text_content = None
            element_id = slot.id or f"slot_{index}"
            elements.append(
                LayoutElement(
                    id=element_id,
                    role=role,
                    content_type=content_type,
                    text_content=text_content,
                    x=slot.x,
                    y=slot.y,
                    width=slot.width,
                    height=slot.height,
                    z_index=index,
                )
            )
            reading_order.append(element_id)
            if hero_id is None and slot.role in {
                TemplateSlotRole.HERO_IMAGE,
                TemplateSlotRole.DRAWING,
                TemplateSlotRole.TITLE,
            }:
                hero_id = element_id
        return LayoutPlan(
            slide_id=slide_id,
            layout_family=family,
            layout_variant=layout.page_type.value,
            page_width=layout.page_width,
            page_height=layout.page_height,
            hero_element_id=hero_id or (reading_order[0] if reading_order else "title"),
            reading_order=reading_order or ["title"],
            whitespace_ratio=0.35,
            elements=elements,
            design_system_id=design_system_id,
            visual_intent_id=uuid4(),
        )

    def _build_imported_design_system(
        self,
        *,
        name: str,
        fonts: list[str],
        colors: list[str],
        source_reference: str,
    ) -> DesignSystem:
        base = default_presentation_design_system()
        primary_font = fonts[0] if fonts else base.typography.title.font_family
        latin_font = next(
            (font for font in fonts if font.lower() in {"arial", "calibri", "helvetica"}),
            base.typography.title.font_family_latin,
        )

        def restyle(token: TextStyleToken) -> TextStyleToken:
            return token.model_copy(
                update={
                    "font_family": primary_font,
                    "font_family_latin": latin_font or token.font_family_latin,
                }
            )

        color_updates: dict[str, str] = {}
        if colors:
            color_updates["background"] = colors[0]
        if len(colors) > 1:
            color_updates["primary_text"] = colors[1]
        if len(colors) > 2:
            color_updates["accent"] = colors[2]
        if len(colors) > 3:
            color_updates["primary"] = colors[3]
        return base.model_copy(
            update={
                "id": uuid4(),
                "name": f"Imported · {name}",
                "description": f"Imported from Template Studio at {datetime.now(UTC).isoformat()}",
                "typography": base.typography.model_copy(
                    update={
                        "display": restyle(base.typography.display),
                        "title": restyle(base.typography.title),
                        "subtitle": restyle(base.typography.subtitle),
                        "heading": restyle(base.typography.heading),
                        "body": restyle(base.typography.body),
                        "caption": restyle(base.typography.caption),
                        "metric": restyle(base.typography.metric),
                        "footnote": restyle(base.typography.footnote),
                        "source": restyle(base.typography.source),
                    }
                ),
                "colors": base.colors.model_copy(update=color_updates),
                "source_type": DesignSystemSource.IMPORTED,
                "source_reference": source_reference,
                "approval_status": ApprovalStatus.DRAFT,
            }
        )

    def _build_recovery_design_system(
        self,
        *,
        name: str,
        scene,
        source_reference: str,
    ) -> DesignSystem:
        fonts = [
            font.family
            for font in scene.font_assets
            if getattr(font, "family", "").strip()
        ]
        colors = self._scene_colors(scene)
        return self._build_imported_design_system(
            name=f"Recovery · {name}",
            fonts=fonts,
            colors=colors,
            source_reference=source_reference,
        )

    def _layout_from_recovery_reference(
        self,
        *,
        source_page_id: str,
        hybrid: HybridRenderScene,
        preview_path: Path,
    ) -> ArchitecturalTemplateLayout:
        slots: list[TemplateSlot] = []
        seen_ids: set[str] = set()
        supports_drawing = False
        supports_photo = False
        supports_metrics = False
        supports_case_reference = False
        architectural_roles: list[str] = []
        for index, region in enumerate(hybrid.regions):
            slot_id = region.source_node_id or f"recovery_slot_{index + 1}"
            if slot_id in seen_ids:
                slot_id = f"{slot_id}_{index + 1}"
            seen_ids.add(slot_id)
            role = _slot_role_from_region(region.region_type, region.semantic_role)
            supports_drawing = supports_drawing or role == TemplateSlotRole.DRAWING
            supports_photo = supports_photo or role in {
                TemplateSlotRole.HERO_IMAGE,
                TemplateSlotRole.SUPPORTING_IMAGE,
            }
            supports_metrics = supports_metrics or role == TemplateSlotRole.METRIC
            supports_case_reference = supports_case_reference or role in {
                TemplateSlotRole.CAPTION,
                TemplateSlotRole.SOURCE,
            }
            if region.semantic_role:
                architectural_roles.append(region.semantic_role)
            slots.append(
                TemplateSlot(
                    id=slot_id,
                    role=role,
                    required=role in {
                        TemplateSlotRole.TITLE,
                        TemplateSlotRole.BODY,
                        TemplateSlotRole.DRAWING,
                    },
                    x=region.bbox.x * hybrid.scene.page_width,
                    y=region.bbox.y * hybrid.scene.page_height,
                    width=region.bbox.width * hybrid.scene.page_width,
                    height=region.bbox.height * hybrid.scene.page_height,
                    accepted_node_types=_accepted_node_types_for_slot(role),
                    accepted_drawing_types=["site_plan"] if role == TemplateSlotRole.DRAWING else [],
                    label=region.semantic_role or role.value,
                    auto_detected=False,
                )
            )
        if not slots:
            slots.append(
                TemplateSlot(
                    id="recovery_body",
                    role=TemplateSlotRole.BODY,
                    required=True,
                    x=0.7,
                    y=0.5,
                    width=8.0,
                    height=0.8,
                    label="recovery_body",
                    auto_detected=False,
                )
            )
        page_type = _template_page_type_from_recovery(hybrid.page_kind)
        return ArchitecturalTemplateLayout(
            name=f"Recovery {source_page_id}",
            description="Saved from Slide Recovery result.",
            page_index=0,
            page_type=page_type,
            suitable_slide_types=[page_type.value],
            suitable_content_types=sorted({slot.role.value for slot in slots}),
            architectural_roles=sorted(set(architectural_roles)),
            slots=slots,
            supports_drawing=supports_drawing,
            supports_photo=supports_photo,
            supports_metrics=supports_metrics,
            supports_case_reference=supports_case_reference,
            minimum_asset_count=sum(
                1
                for slot in slots
                if slot.role
                in {
                    TemplateSlotRole.HERO_IMAGE,
                    TemplateSlotRole.SUPPORTING_IMAGE,
                    TemplateSlotRole.DRAWING,
                    TemplateSlotRole.CHART,
                    TemplateSlotRole.TABLE,
                }
            ),
            maximum_asset_count=max(1, len(slots)),
            preview_image_path=str(preview_path),
            page_width=hybrid.scene.page_width,
            page_height=hybrid.scene.page_height,
            extracted_fonts=[font.family for font in hybrid.scene.font_assets if font.family],
            extracted_colors=self._scene_colors(hybrid.scene),
            classification_confidence=0.9,
            classification_notes="slide recovery reference export",
        )

    def _scene_colors(self, scene) -> list[str]:
        colors: list[str] = []
        if getattr(scene.background, "color", ""):
            colors.append(scene.background.color)
        for node in scene.nodes:
            for attr in ("color", "fill_color", "stroke_color"):
                value = getattr(node, attr, None)
                if isinstance(value, str) and value.strip():
                    colors.append(value.strip())
        return list(dict.fromkeys(colors))[:16]

    def _require_template(self, template_id: UUID) -> ArchitecturalTemplate:
        template = self._templates.get(template_id)
        if template is None:
            raise WorkflowError(f"模板不存在：{template_id}")
        return template

    def _save(self, template: ArchitecturalTemplate) -> ArchitecturalTemplate:
        saved = self._templates.save(template.model_copy(update={"updated_at": datetime.now(UTC)}))
        self._write_manifest(saved)
        return saved

    def _write_manifest(self, template: ArchitecturalTemplate) -> None:
        workspace = Path(template.workspace_dir or self.workspace_root(template.id))
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "template.json").write_text(
            json.dumps(template.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _template_page_type_from_recovery(page_kind: SlideRecoveryPageKind) -> TemplatePageType:
    mapping = {
        SlideRecoveryPageKind.TITLE: TemplatePageType.COVER,
        SlideRecoveryPageKind.IMAGE_TEXT: TemplatePageType.TEXT_ARGUMENT,
        SlideRecoveryPageKind.TABLE: TemplatePageType.METRIC,
        SlideRecoveryPageKind.PHOTO: TemplatePageType.PHOTO_GRID,
        SlideRecoveryPageKind.DRAWING_DOMINANT: TemplatePageType.DRAWING_FOCUS,
    }
    return mapping.get(page_kind, TemplatePageType.UNKNOWN)


def _slot_role_from_region(region_type: str, semantic_role: str | None) -> TemplateSlotRole:
    role_text = (semantic_role or "").lower()
    if "title" in role_text:
        return TemplateSlotRole.TITLE
    if "subtitle" in role_text:
        return TemplateSlotRole.SUBTITLE
    if "caption" in role_text:
        return TemplateSlotRole.CAPTION
    if "source" in role_text:
        return TemplateSlotRole.SOURCE
    if "metric" in role_text:
        return TemplateSlotRole.METRIC
    if "table" in role_text or region_type == "table":
        return TemplateSlotRole.TABLE
    if "chart" in role_text or region_type == "chart":
        return TemplateSlotRole.CHART
    if region_type == "drawing":
        return TemplateSlotRole.DRAWING
    if region_type == "image":
        return TemplateSlotRole.HERO_IMAGE
    if region_type in {"line", "shape", "background"}:
        return TemplateSlotRole.DECORATION
    return TemplateSlotRole.BODY


def _accepted_node_types_for_slot(role: TemplateSlotRole) -> list[str]:
    if role in {TemplateSlotRole.TITLE, TemplateSlotRole.SUBTITLE, TemplateSlotRole.BODY}:
        return ["text"]
    if role == TemplateSlotRole.DRAWING:
        return ["drawing"]
    if role in {TemplateSlotRole.HERO_IMAGE, TemplateSlotRole.SUPPORTING_IMAGE}:
        return ["image"]
    if role == TemplateSlotRole.TABLE:
        return ["table", "text"]
    if role == TemplateSlotRole.CHART:
        return ["chart", "image"]
    if role == TemplateSlotRole.DECORATION:
        return ["shape"]
    return ["text", "image"]
