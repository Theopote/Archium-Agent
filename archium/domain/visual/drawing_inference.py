"""Infer whether a reference picture is an architectural drawing vs a photo."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from archium.domain.visual.reference_slide import ReferenceElement, ReferenceElementType

_DRAWING_TOKENS = (
    "总平面",
    "总图",
    "平面图",
    "平面",
    "剖面",
    "立面",
    "轴测",
    "流线",
    "图纸",
    "详图",
    "大样",
    "首层",
    "标准层",
    "地下室",
    "场地平面",
    "site plan",
    "floor plan",
    "section",
    "elevation",
    "drawing",
    "plan view",
)

_PHOTO_TOKENS = (
    "现场",
    "照片",
    "实景",
    "航拍",
    "效果图",
    "人视",
    "photo",
    "photograph",
    "before",
    "after",
    "改造前",
    "改造后",
)

_TOKEN_RE = re.compile(
    "|".join(re.escape(t) for t in sorted(_DRAWING_TOKENS, key=len, reverse=True)),
    re.I,
)
_PHOTO_RE = re.compile(
    "|".join(re.escape(t) for t in sorted(_PHOTO_TOKENS, key=len, reverse=True)),
    re.I,
)


@dataclass(frozen=True)
class DrawingInferenceResult:
    is_drawing: bool
    confidence: float
    evidence: list[str]
    needs_review: bool = False


class DrawingInferenceService:
    """Promote IMAGE → DRAWING using neighborhood cues (not picture text frame)."""

    def infer(
        self,
        image_element: ReferenceElement,
        neighboring_text_elements: list[ReferenceElement],
        *,
        slide_title: str = "",
        slide_notes: str = "",
        proximity_inches: float = 1.25,
    ) -> DrawingInferenceResult:
        if image_element.element_type not in {
            ReferenceElementType.IMAGE,
            ReferenceElementType.DRAWING,
        }:
            return DrawingInferenceResult(False, 0.0, ["not an image element"])

        score = 0.0
        photo_score = 0.0
        evidence: list[str] = []

        # Shape name (high signal — architects often name pictures).
        name_hit = _match_tokens(image_element.source_shape_name)
        if name_hit:
            score += 0.45
            evidence.append(f"shape_name:{name_hit}")

        # Alt text / description stored on the element.
        alt = (image_element.alt_text or "").strip()
        if not alt:
            for note in image_element.style_notes:
                if note.startswith("alt:"):
                    alt = note[4:].strip()
                    break
        if not alt and image_element.text:
            alt = image_element.text
        alt_hit = _match_tokens(alt)
        if alt_hit:
            score += 0.4
            evidence.append(f"alt_text:{alt_hit}")
        photo_hit = _match_photo_tokens(alt) or _match_photo_tokens(
            image_element.source_shape_name
        )
        if photo_hit:
            photo_score += 0.5
            evidence.append(f"photo_cue:{photo_hit}")

        # Slide title / notes.
        title_hit = _match_tokens(slide_title)
        if title_hit:
            score += 0.25
            evidence.append(f"slide_title:{title_hit}")
        notes_hit = _match_tokens(slide_notes)
        if notes_hit:
            score += 0.15
            evidence.append(f"slide_notes:{notes_hit}")
        if _match_photo_tokens(slide_title):
            photo_score += 0.25
            evidence.append("slide_title:photo")

        # Neighboring captions / labels by spatial proximity.
        neighbors = self._nearby_texts(
            image_element, neighboring_text_elements, proximity_inches=proximity_inches
        )
        for neighbor, distance in neighbors[:6]:
            hit = _match_tokens(neighbor.text)
            if hit:
                weight = 0.35 if distance <= 0.6 else 0.22
                if neighbor.semantic_role in {"caption", "title", "subtitle"}:
                    weight += 0.1
                score += weight
                evidence.append(f"neighbor[{neighbor.semantic_role or 'text'}]:{hit}")
            photo_n = _match_photo_tokens(neighbor.text)
            if photo_n:
                photo_score += 0.3
                evidence.append(f"neighbor_photo:{photo_n}")

        # Aspect / size heuristics (weak).
        aspect = image_element.width / max(image_element.height, 0.01)
        area = image_element.width * image_element.height
        if 0.7 <= aspect <= 2.2 and area >= 6.0:
            score += 0.08
            evidence.append("large_plan_like_aspect")
        if aspect >= 2.8:
            photo_score += 0.1
            evidence.append("wide_cinematic_aspect")

        net = score - photo_score
        is_drawing = net >= 0.35 and score >= 0.35
        confidence = max(0.0, min(1.0, 0.5 + net))
        needs_review = (0.25 <= abs(net) < 0.45) or (
            score > 0 and photo_score > 0 and abs(score - photo_score) < 0.2
        )
        if is_drawing and not evidence:
            evidence.append("heuristic")
        return DrawingInferenceResult(
            is_drawing=is_drawing,
            confidence=round(confidence, 3),
            evidence=evidence,
            needs_review=needs_review,
        )

    def refine_slide_elements(
        self,
        elements: list[ReferenceElement],
        *,
        slide_title: str = "",
        slide_notes: str = "",
    ) -> list[ReferenceElement]:
        """Mutate IMAGE elements in-place when drawing cues are strong enough."""
        text_elements = [
            e
            for e in elements
            if e.element_type == ReferenceElementType.TEXT and e.text.strip()
        ]
        if not slide_title:
            slide_title = _extract_slide_title(text_elements)

        for element in elements:
            if element.element_type != ReferenceElementType.IMAGE:
                continue
            result = self.infer(
                element,
                text_elements,
                slide_title=slide_title,
                slide_notes=slide_notes,
            )
            if result.is_drawing:
                element.element_type = ReferenceElementType.DRAWING
                element.semantic_role = "drawing"
                element.style_notes = [
                    *element.style_notes,
                    f"drawing_inference:{','.join(result.evidence[:4])}",
                    f"drawing_confidence:{result.confidence:.2f}",
                ]
                if result.needs_review:
                    element.style_notes.append("drawing_needs_review")
            elif result.needs_review:
                element.style_notes = [
                    *element.style_notes,
                    "drawing_ambiguous_needs_review",
                    *result.evidence[:3],
                ]
        return elements

    def _nearby_texts(
        self,
        image: ReferenceElement,
        texts: list[ReferenceElement],
        *,
        proximity_inches: float,
    ) -> list[tuple[ReferenceElement, float]]:
        scored: list[tuple[ReferenceElement, float]] = []
        for text in texts:
            dist = _box_distance(image, text)
            if dist <= proximity_inches:
                scored.append((text, dist))
                continue
            under = (
                text.y >= image.y + image.height - 0.15
                and text.y <= image.y + image.height + 1.6
                and _horizontal_overlap(image, text) >= 0.25
            )
            if under:
                scored.append((text, dist))
        scored.sort(key=lambda item: item[1])
        return scored


def _match_tokens(text: str) -> str | None:
    if not text:
        return None
    normalized = _normalize_label(text)
    match = _TOKEN_RE.search(normalized)
    return match.group(0) if match else None


def _match_photo_tokens(text: str) -> str | None:
    if not text:
        return None
    normalized = _normalize_label(text)
    match = _PHOTO_RE.search(normalized)
    return match.group(0) if match else None


def _normalize_label(text: str) -> str:
    """Normalize CamelCase / snake_case labels so SitePlan → site plan."""
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    spaced = spaced.replace("_", " ").replace("-", " ")
    return spaced


def _extract_slide_title(texts: list[ReferenceElement]) -> str:
    titled = [t for t in texts if t.semantic_role == "title"]
    if titled:
        return titled[0].text
    if not texts:
        return ""
    ranked = sorted(
        texts,
        key=lambda t: (
            -(t.font_size_pt or 0),
            t.y,
        ),
    )
    return ranked[0].text if ranked else ""


def _box_distance(a: ReferenceElement, b: ReferenceElement) -> float:
    """Axis-aligned gap between boxes (0 if overlapping)."""
    dx = max(a.x - (b.x + b.width), b.x - (a.x + a.width), 0.0)
    dy = max(a.y - (b.y + b.height), b.y - (a.y + a.height), 0.0)
    return math.hypot(dx, dy)


def _horizontal_overlap(a: ReferenceElement, b: ReferenceElement) -> float:
    left = max(a.x, b.x)
    right = min(a.x + a.width, b.x + b.width)
    overlap = max(0.0, right - left)
    return overlap / max(min(a.width, b.width), 0.01)
