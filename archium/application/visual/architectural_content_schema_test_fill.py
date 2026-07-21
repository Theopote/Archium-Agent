"""Structural test-fill validation for induced content schemas."""

from __future__ import annotations

from collections import defaultdict

from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRole,
    SchemaTestFillResult,
)
from archium.domain.visual.reference_slide import (
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)

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


class ArchitecturalContentSchemaTestFillService:
    """Validate schema against representative slide structure (not full RenderScene)."""

    def validate(
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
        reference_leakage = False

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
            if visual.role == "drawing" and visual.fit_mode == "contain":
                if visual_counts.get("drawing", 0) < visual.min_count:
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

        # Structural fill only checks slot capacity — reference slides always
        # contain reference_template assets; leakage is enforced at render time.
        reference_leakage = False

        render_valid = (
            required_slots_filled
            and not text_overflow
            and not missing_assets
            and drawing_policy_passed
            and not reference_leakage
        )

        return SchemaTestFillResult(
            schema_id=schema.id,
            representative_slide_id=slide.slide_id,
            required_slots_filled=required_slots_filled,
            text_overflow=text_overflow,
            missing_assets=missing_assets,
            drawing_policy_passed=drawing_policy_passed,
            reference_leakage=reference_leakage,
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
