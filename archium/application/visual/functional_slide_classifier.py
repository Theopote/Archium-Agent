"""Functional and architectural content classification for reference slides."""

from __future__ import annotations

from archium.domain.visual.reference_slide import (
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideClassification,
    FunctionalSlideType,
)

_LOW_CONFIDENCE = 0.55


class FunctionalSlideClassifier:
    """Heuristic functional + content typing for reference pages."""

    def classify_all(
        self,
        slides: list[ReferenceSlideSnapshot],
    ) -> list[FunctionalSlideClassification]:
        total = len(slides)
        return [self.classify(slide, deck_size=total) for slide in slides]

    def classify(
        self,
        slide: ReferenceSlideSnapshot,
        *,
        deck_size: int,
    ) -> FunctionalSlideClassification:
        text_blob = " ".join(slide.text_content)
        lower = text_blob.lower()
        evidence: list[str] = []
        functional = FunctionalSlideType.UNKNOWN
        content = ArchitecturalContentType.UNKNOWN
        confidence = 0.25

        # --- Functional ---
        if slide.slide_index == 0:
            functional = FunctionalSlideType.COVER
            confidence = 0.75
            evidence.append("first page")
            content = ArchitecturalContentType.COVER_VISUAL
        elif any(k in text_blob for k in ("目录", "议程")) or "agenda" in lower:
            functional = FunctionalSlideType.AGENDA
            confidence = 0.85
            evidence.append("agenda keyword")
            content = ArchitecturalContentType.TEXT_ARGUMENT
        elif any(k in text_blob for k in ("附录", "attachment")) or "appendix" in lower:
            functional = FunctionalSlideType.APPENDIX
            confidence = 0.7
            evidence.append("appendix keyword")
        elif any(k in text_blob for k in ("决策", "请示", "建议批准")) or "decision" in lower:
            functional = FunctionalSlideType.DECISION
            confidence = 0.7
            evidence.append("decision keyword")
            content = ArchitecturalContentType.CONCLUSION
        elif any(
            k in text_blob for k in ("执行摘要", "核心结论", "汇报摘要")
        ) or "executive summary" in lower:
            functional = FunctionalSlideType.EXECUTIVE_SUMMARY
            confidence = 0.7
            evidence.append("executive summary keyword")
            content = ArchitecturalContentType.STRATEGY
        elif any(k in text_blob for k in ("谢谢", "致谢", "结束")) or "thank" in lower:
            functional = FunctionalSlideType.CLOSING
            confidence = 0.75
            evidence.append("closing keyword")
            content = ArchitecturalContentType.CONCLUSION
        elif (
            slide.slide_index >= deck_size - 1
            and len(slide.text_content) <= 3
            and slide.image_count <= 1
        ):
            functional = FunctionalSlideType.CLOSING
            confidence = 0.55
            evidence.append("last sparse page")
            content = ArchitecturalContentType.CONCLUSION
        elif (
            len(slide.text_content) <= 2
            and slide.image_count <= 1
            and slide.text_length < 80
            and slide.slide_index > 0
        ):
            functional = FunctionalSlideType.SECTION_DIVIDER
            confidence = 0.55
            evidence.append("sparse section candidate")
            content = ArchitecturalContentType.SECTION_VISUAL
        else:
            functional = FunctionalSlideType.CONTENT
            confidence = 0.65
            evidence.append("default content page")

        # --- Content type (may refine cover/section already set) ---
        if functional == FunctionalSlideType.CONTENT or content == ArchitecturalContentType.UNKNOWN:
            content, c_conf, c_ev = self._classify_content(slide, text_blob, lower)
            evidence.extend(c_ev)
            if functional == FunctionalSlideType.CONTENT:
                confidence = min(0.95, (confidence + c_conf) / 2 + 0.1)
            elif content == ArchitecturalContentType.UNKNOWN:
                content = ArchitecturalContentType.UNKNOWN

        needs_review = confidence < _LOW_CONFIDENCE or functional == FunctionalSlideType.UNKNOWN
        if slide.parse_warnings:
            needs_review = True
            evidence.append("parse warnings present")
            confidence = min(confidence, 0.45)

        return FunctionalSlideClassification(
            slide_id=slide.slide_id,
            slide_index=slide.slide_index,
            functional_type=functional,
            content_type=content,
            confidence=round(confidence, 3),
            evidence=evidence,
            needs_review=needs_review,
        )

    def _classify_content(
        self,
        slide: ReferenceSlideSnapshot,
        text_blob: str,
        lower: str,
    ) -> tuple[ArchitecturalContentType, float, list[str]]:
        evidence: list[str] = []
        drawing = any(
            e.element_type == ReferenceElementType.DRAWING
            or e.semantic_role == "drawing"
            for e in slide.elements
        )
        if drawing or any(k in text_blob for k in ("总平面", "平面图", "剖面", "立面")):
            evidence.append("drawing cues")
            return ArchitecturalContentType.DRAWING_FOCUS, 0.75, evidence
        if slide.image_count >= 4:
            evidence.append("multi-image grid")
            return ArchitecturalContentType.MULTI_IMAGE_GRID, 0.8, evidence
        if slide.image_count >= 2 and (
            any(k in text_blob for k in ("前后", "改造前", "改造后"))
            or ("before" in lower and "after" in lower)
        ):
            evidence.append("before/after cues")
            return ArchitecturalContentType.BEFORE_AFTER, 0.75, evidence
        if slide.image_count >= 2 and any(
            k in text_blob for k in ("对比", "案例", "对标")
        ):
            evidence.append("case comparison cues")
            return ArchitecturalContentType.CASE_COMPARISON, 0.7, evidence
        if slide.image_count >= 1 and any(
            k in text_blob for k in ("现场", "现状", "问题")
        ):
            evidence.append("photo analysis cues")
            return ArchitecturalContentType.PHOTO_ANALYSIS, 0.7, evidence
        if any(e.semantic_role == "metric" for e in slide.elements) or sum(
            ch.isdigit() for ch in text_blob
        ) > 20:
            evidence.append("metric cues")
            return ArchitecturalContentType.METRIC_SUMMARY, 0.7, evidence
        if slide.chart_count > 0:
            evidence.append("chart present")
            return ArchitecturalContentType.DIAGRAM, 0.65, evidence
        if any(k in text_blob for k in ("时间线", "阶段", "里程碑")) or "timeline" in lower:
            evidence.append("timeline cues")
            return ArchitecturalContentType.TIMELINE, 0.7, evidence
        if any(k in text_blob for k in ("流程", "步骤", "路径")) or "process" in lower:
            evidence.append("process cues")
            return ArchitecturalContentType.PROCESS, 0.65, evidence
        if any(k in text_blob for k in ("策略", "原则", "目标")):
            evidence.append("strategy cues")
            return ArchitecturalContentType.STRATEGY, 0.6, evidence
        if slide.image_count >= 1 and slide.text_length > 40:
            evidence.append("image+text hybrid")
            return ArchitecturalContentType.IMAGE_TEXT_HYBRID, 0.65, evidence
        if slide.image_count == 0 and slide.text_length > 60:
            evidence.append("text argument")
            return ArchitecturalContentType.TEXT_ARGUMENT, 0.7, evidence
        evidence.append("insufficient content signals")
        return ArchitecturalContentType.UNKNOWN, 0.3, evidence
