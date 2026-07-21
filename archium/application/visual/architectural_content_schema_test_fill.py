"""Structural + RenderScene test-fill validation for induced content schemas."""

from __future__ import annotations

from collections import defaultdict
from uuid import uuid4

from archium.application.visual.reference_slide_editing_service import ReferenceSlideEditingService
from archium.application.visual.scene_proposal_qa import findings_to_quality_issues
from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
from archium.application.visual.semantic_content_plan import expand_visual_evidence_roles
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRequirement,
    ContentRole,
    SchemaTestFillResult,
)
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateStatus,
)
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.page_quality import IssueSeverity
from archium.domain.visual.reference_slide import (
    REFERENCE_TEMPLATE_ASSET_ORIGIN,
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.render_scene import DrawingNode, ImageNode, RenderScene
from archium.domain.visual.scene_qa import SceneSemanticCheckCode

_ROLE_SEMANTICS: dict[ContentRole, set[str]] = {
    ContentRole.TITLE: {"title"},
    ContentRole.BODY: {"body", "subtitle"},
    ContentRole.CENTRAL_CLAIM: {"title", "body"},
    ContentRole.EVIDENCE: {"body", "caption", "subtitle"},
    ContentRole.METRIC: {"metric"},
    ContentRole.CAPTION: {"caption"},
    ContentRole.SOURCE: {"source"},
    ContentRole.DECISION_REQUEST: {"body", "title"},
    ContentRole.LEAD_STATEMENT: {"subtitle", "body"},
    ContentRole.INTERPRETATION: {"body", "caption"},
}

_FILL_SENTENCE = "测试填充内容，用于验证 Schema 能否编译为 RenderScene。"


class ArchitecturalContentSchemaTestFillService:
    """Validate schema against representative slide structure and RenderScene QA."""

    def __init__(
        self,
        *,
        render_validate: bool = True,
        editor: ReferenceSlideEditingService | None = None,
    ) -> None:
        self._render_validate = render_validate
        self._editor = editor or ReferenceSlideEditingService()

    def validate(
        self,
        schema: ArchitecturalContentSchema,
        slide: ReferenceSlideSnapshot,
    ) -> SchemaTestFillResult:
        result = self._validate_structure(schema, slide)
        if not self._render_validate or not result.required_slots_filled:
            return result
        return self._merge_render_validation(schema, slide, result)

    def _validate_structure(
        self,
        schema: ArchitecturalContentSchema,
        slide: ReferenceSlideSnapshot,
    ) -> SchemaTestFillResult:
        blockers: list[str] = []
        warnings: list[str] = []
        text_by_role = self._text_elements_by_role(slide)
        visual_counts = self._visual_counts(slide)

        required_slots_filled = True
        text_overflow = False
        missing_assets = False
        drawing_policy_passed = True

        for requirement in schema.required_content:
            if not requirement.required:
                continue
            roles = _ROLE_SEMANTICS.get(requirement.role, {requirement.role.value})
            candidates = [el for role in roles for el in text_by_role.get(role, [])]
            if len(candidates) < requirement.min_count:
                required_slots_filled = False
                blockers.append(
                    f"缺少 {requirement.role.value} 槽位 "
                    f"(需要 {requirement.min_count}，现有 {len(candidates)})"
                )
                continue
            for element in candidates[: requirement.max_count]:
                text_len = len((element.text or "").strip())
                if text_len and requirement.min_length and text_len < requirement.min_length:
                    blockers.append(
                        f"{requirement.role.value} 文本低于下限 "
                        f"({text_len} < {requirement.min_length})"
                    )
                if text_len and text_len > requirement.max_length:
                    text_overflow = True
                    blockers.append(
                        f"{requirement.role.value} 文本超出上限 "
                        f"({text_len} > {requirement.max_length})"
                    )

        for requirement in schema.evidence_items:
            if not requirement.required:
                continue
            roles = _ROLE_SEMANTICS.get(requirement.role, {requirement.role.value})
            candidates = [el for role in roles for el in text_by_role.get(role, [])]
            if len(candidates) < requirement.min_count:
                required_slots_filled = False
                blockers.append(
                    f"缺少证据项 {requirement.label or requirement.role.value} "
                    f"(需要 {requirement.min_count}，现有 {len(candidates)})"
                )

        for visual in schema.visual_requirements:
            if not visual.required:
                continue
            available = self._count_visual_role(visual.role, visual_counts)
            if available < visual.min_count:
                missing_assets = True
                blockers.append(
                    f"缺少 {visual.role} 视觉槽位 "
                    f"(需要 {visual.min_count}，现有 {available})"
                )
            if (
                visual.role == "drawing"
                and visual.fit_mode == "contain"
                and visual_counts.get("drawing", 0) < visual.min_count
            ):
                drawing_policy_passed = False

        for visual in schema.visual_evidence:
            if not visual.required:
                continue
            available = self._count_visual_role(visual.role, visual_counts)
            if available < visual.min_count:
                missing_assets = True
                blockers.append(
                    f"缺少视觉证据 {visual.description or visual.role} "
                    f"(需要 {visual.min_count}，现有 {available})"
                )

        if not slide.elements:
            required_slots_filled = False
            blockers.append("代表页无可用元素")

        render_valid = (
            required_slots_filled
            and not text_overflow
            and not missing_assets
            and drawing_policy_passed
        )

        return SchemaTestFillResult(
            schema_id=schema.id,
            representative_slide_id=slide.slide_id,
            required_slots_filled=required_slots_filled,
            text_overflow=text_overflow,
            missing_assets=missing_assets,
            drawing_policy_passed=drawing_policy_passed,
            reference_leakage=False,
            scene_compiled=False,
            render_valid=render_valid,
            blockers=blockers,
            warnings=warnings,
        )

    def _merge_render_validation(
        self,
        schema: ArchitecturalContentSchema,
        slide: ReferenceSlideSnapshot,
        structural: SchemaTestFillResult,
    ) -> SchemaTestFillResult:
        blockers = list(structural.blockers)
        warnings = list(structural.warnings)
        text_overflow = structural.text_overflow
        missing_assets = structural.missing_assets
        drawing_policy_passed = structural.drawing_policy_passed
        reference_leakage = False
        scene_compiled = False

        try:
            edit_result = self._editor.generate_scene(
                reference_slide=slide,
                content_schema=schema,
                slide_spec=build_test_fill_slide_spec(schema),
                assets=build_test_fill_assets(schema),
                design_system=default_presentation_design_system(),
                template=build_test_fill_template(schema),
                presentation_id=uuid4(),
            )
        except Exception as exc:  # noqa: BLE001 — publish gate must surface compile failures
            blockers.append(f"RenderScene 编译失败：{exc}")
            return structural.model_copy(
                update={
                    "blockers": blockers,
                    "warnings": warnings,
                    "render_valid": False,
                }
            )

        scene = edit_result.scene
        scene_compiled = True
        if edit_result.warnings:
            warnings.extend(edit_result.warnings[:3])

        reference_leakage = _scene_has_reference_template_leak(scene)
        if reference_leakage:
            blockers.append("RenderScene 仍包含 reference_template 素材")

        qa_issues = findings_to_quality_issues(
            [
                finding
                for finding in run_scene_semantic_qa(
                    uuid4(),
                    [scene],
                    slide_orders={scene.slide_id: 0},
                ).findings
                if finding.slide_id == scene.slide_id
            ]
        )
        for issue in qa_issues:
            if issue.code == SceneSemanticCheckCode.TEXT_OVERFLOW:
                text_overflow = True
            if issue.code == SceneSemanticCheckCode.IMAGE_NOT_RENDERED:
                missing_assets = True
            if issue.code == SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN:
                drawing_policy_passed = False

            message = issue.message or issue.code
            if issue.severity in {IssueSeverity.BLOCKER, IssueSeverity.MAJOR}:
                blockers.append(message)
            else:
                warnings.append(message)

        render_valid = (
            structural.required_slots_filled
            and not text_overflow
            and not missing_assets
            and drawing_policy_passed
            and not reference_leakage
            and scene_compiled
            and not any(
                issue.severity in {IssueSeverity.BLOCKER, IssueSeverity.MAJOR}
                for issue in qa_issues
            )
        )

        return SchemaTestFillResult(
            schema_id=schema.id,
            representative_slide_id=slide.slide_id,
            required_slots_filled=structural.required_slots_filled,
            text_overflow=text_overflow,
            missing_assets=missing_assets,
            drawing_policy_passed=drawing_policy_passed,
            reference_leakage=reference_leakage,
            scene_compiled=scene_compiled,
            render_valid=render_valid,
            blockers=blockers,
            warnings=warnings,
        )

    def _text_elements_by_role(
        self, slide: ReferenceSlideSnapshot
    ) -> dict[str, list[ReferenceElement]]:
        grouped: dict[str, list[ReferenceElement]] = defaultdict(list)
        text_elements: list[ReferenceElement] = []
        for element in slide.iter_elements():
            if element.element_type != ReferenceElementType.TEXT:
                continue
            text_elements.append(element)
            role = (element.semantic_role or "").strip().lower()
            if role:
                grouped[role].append(element)

        if not grouped.get("title") and text_elements:
            top = min(
                text_elements,
                key=lambda e: (e.y, -(e.font_size_pt or 0), -len(e.text or "")),
            )
            grouped["title"].append(top)

        if not grouped.get("caption"):
            page_height = getattr(slide, "height", None) or getattr(slide, "page_height", None) or 7.5
            bottom = [
                e
                for e in text_elements
                if e.y >= page_height * 0.78 and (e.text or "").strip()
            ]
            if bottom:
                grouped["caption"].extend(bottom)

        return grouped

    def _visual_counts(self, slide: ReferenceSlideSnapshot) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for element in slide.iter_elements():
            if element.likely_background_or_decoration:
                continue
            if element.element_type == ReferenceElementType.DRAWING or element.semantic_role == "drawing":
                counts["drawing"] += 1
            elif element.element_type == ReferenceElementType.IMAGE:
                role = (element.semantic_role or "supporting_image").lower()
                counts[role] += 1
                counts["image"] += 1
                if role in {"hero_image", "hero"}:
                    counts["hero_image"] += 1
        return counts

    def _count_visual_role(self, role: str, counts: dict[str, int]) -> int:
        role_key = role.lower()
        if role_key == "drawing":
            return counts.get("drawing", 0)
        if role_key in {"hero_image", "hero"}:
            return counts.get("hero_image", 0) or counts.get("image", 0)
        if role_key in {"supporting_image", "multi_image_grid", "before_after_pair"}:
            return counts.get("image", 0)
        return counts.get(role_key, 0)


def build_test_fill_slide_spec(schema: ArchitecturalContentSchema) -> SlideSpec:
    """Synthetic SlideSpec sized to satisfy schema communication contract."""
    hydrated = schema.hydrate_semantic_contract()
    presentation_id = uuid4()
    title = schema.name.replace("/", " ").strip() or "测试页标题"
    message = _placeholder_for_requirement(
        hydrated.central_claim,
        fallback=schema.page_purpose or _FILL_SENTENCE,
        default_max=120,
    )
    key_points: list[str] = []
    for requirement in hydrated.evidence_items:
        if requirement.role != ContentRole.EVIDENCE:
            continue
        repeat = max(requirement.min_count, 1) if requirement.required else requirement.min_count
        for _ in range(repeat):
            key_points.append(
                _placeholder_for_requirement(
                    requirement,
                    fallback=f"证据项 {requirement.label or requirement.role.value}",
                    default_max=80,
                )
            )
    for requirement in hydrated.required_content:
        if requirement.role not in {ContentRole.BODY, ContentRole.EVIDENCE, ContentRole.METRIC}:
            continue
        repeat = max(requirement.min_count, 1) if requirement.required else requirement.min_count
        for _ in range(repeat):
            key_points.append(
                _placeholder_for_requirement(
                    requirement,
                    fallback=_FILL_SENTENCE,
                    default_max=80,
                )
            )
    if not key_points:
        key_points.append(_placeholder_text(min_len=12, max_len=80))

    return SlideSpec(
        presentation_id=presentation_id,
        chapter_id="schema_test_fill",
        order=0,
        title=title[:120],
        message=message,
        key_points=key_points[:6],
        speaker_notes=_placeholder_text(min_len=8, max_len=60),
    )


def build_test_fill_template(schema: ArchitecturalContentSchema) -> ArchitecturalTemplate:
    page_type = TemplatePageType.PHOTO_GRID
    if schema.content_type.value == "drawing_focus":
        page_type = TemplatePageType.DRAWING_FOCUS
    elif schema.functional_type.value == "cover":
        page_type = TemplatePageType.COVER
    layout = ArchitecturalTemplateLayout(
        name=schema.name,
        page_index=0,
        page_type=page_type,
        suitable_content_types=[schema.content_type.value],
        content_schema_id=schema.id,
        representative_slide_id=schema.representative_slide_id,
        cluster_id=schema.cluster_id,
    )
    return ArchitecturalTemplate(
        id=uuid4(),
        name=f"test-fill-{schema.id[:8]}",
        layouts=[layout],
        content_schemas=[schema],
        status=TemplateStatus.DRAFT,
    )


def build_test_fill_assets(schema: ArchitecturalContentSchema) -> list[Asset]:
    """Placeholder project assets for visual slots required by the schema."""
    project_id = uuid4()
    assets: list[Asset] = []
    for index, role in enumerate(expand_visual_evidence_roles(schema)):
        if role == "drawing":
            assets.append(
                Asset(
                    id=uuid4(),
                    project_id=project_id,
                    filename=f"test_drawing_{index}.png",
                    path=f"benchmark://schema_test_fill/drawing_{index}.png",
                    asset_type=AssetType.DRAWING,
                )
            )
        else:
            assets.append(
                Asset(
                    id=uuid4(),
                    project_id=project_id,
                    filename=f"test_photo_{index}.jpg",
                    path=f"benchmark://schema_test_fill/photo_{index}.jpg",
                    asset_type=AssetType.PHOTO,
                )
            )
    return assets


def _placeholder_for_requirement(
    requirement: ContentRequirement | None,
    *,
    fallback: str,
    default_max: int,
) -> str:
    if requirement is None:
        return _placeholder_text(min_len=8, max_len=default_max)
    min_len = max(requirement.min_length, 8)
    max_len = max(requirement.max_length, min_len)
    return _placeholder_text(min_len=min_len, max_len=max_len)


def _placeholder_text(*, min_len: int, max_len: int) -> str:
    text = _FILL_SENTENCE
    while len(text) < min_len:
        text += _FILL_SENTENCE
    return text[:max_len]


def _scene_has_reference_template_leak(scene: RenderScene) -> bool:
    for node in scene.nodes:
        if isinstance(node, ImageNode) and node.asset_origin == REFERENCE_TEMPLATE_ASSET_ORIGIN:
            return True
        if isinstance(node, DrawingNode):
            for ref in scene.asset_manifest:
                if ref.origin == REFERENCE_TEMPLATE_ASSET_ORIGIN and ref.asset_id == node.asset_id:
                    return True
    return any(ref.origin == REFERENCE_TEMPLATE_ASSET_ORIGIN for ref in scene.asset_manifest)
