"""Functional and architectural content classification for reference slides.

V1 scope (honest):
    This is a **rule-driven structural induction** classifier. It combines text
    keywords, element counts, sparsity, and light neighbor context. It does
    **not** perform full visual-semantic induction from screenshots or VLM
    embeddings. Screenshot paths and visual_embedding remain available for
    later phases; they are not the decision core here.
"""

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

# Open review when confidence is strictly below this threshold.
_LOW_CONFIDENCE = 0.55

_DISCLAIMER_TOKENS = (
    "免责",
    "声明",
    "保密",
    "仅供内部",
    "disclaimer",
    "confidential",
    "内部资料",
    "版权所有",
)


class FunctionalSlideClassifier:
    """Heuristic functional + content typing for reference pages (rule-driven V1)."""

    def classify_all(
        self,
        slides: list[ReferenceSlideSnapshot],
    ) -> list[FunctionalSlideClassification]:
        total = len(slides)
        results: list[FunctionalSlideClassification] = []
        for index, slide in enumerate(slides):
            prev_slide = slides[index - 1] if index > 0 else None
            next_slide = slides[index + 1] if index + 1 < total else None
            results.append(
                self.classify(
                    slide,
                    deck_size=total,
                    previous_slide=prev_slide,
                    next_slide=next_slide,
                )
            )
        return results

    def classify(
        self,
        slide: ReferenceSlideSnapshot,
        *,
        deck_size: int,
        previous_slide: ReferenceSlideSnapshot | None = None,
        next_slide: ReferenceSlideSnapshot | None = None,
    ) -> FunctionalSlideClassification:
        text_blob = " ".join(slide.text_content)
        lower = text_blob.lower()
        evidence: list[str] = []
        functional = FunctionalSlideType.UNKNOWN
        content = ArchitecturalContentType.UNKNOWN
        confidence = 0.25
        force_review = False

        # Strong lexical signals first — including on page 0 (first page is only a prior).
        if any(k in text_blob for k in ("目录", "议程")) or "agenda" in lower:
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
        elif _has_disclaimer(text_blob, lower):
            functional = FunctionalSlideType.CONTENT
            confidence = 0.55
            evidence.append("disclaimer / fixed front-matter cues")
            content = ArchitecturalContentType.TEXT_ARGUMENT
            force_review = True
            if slide.slide_index == 0:
                evidence.append("first-page prior overridden by disclaimer")
        elif slide.slide_index == 0:
            # First-page prior — not an absolute cover conclusion.
            functional, content, confidence, prior_evidence, prior_review = (
                self._apply_first_page_prior(slide, text_blob)
            )
            evidence.extend(prior_evidence)
            force_review = force_review or prior_review
        elif (
            slide.slide_index >= deck_size - 1
            and len(slide.text_content) <= 3
            and slide.image_count <= 1
        ):
            functional = FunctionalSlideType.CLOSING
            confidence = 0.5
            evidence.append("last sparse page")
            content = ArchitecturalContentType.CONCLUSION
            force_review = True
        elif self._is_sparse_candidate(slide):
            functional, content, confidence, sparse_evidence, sparse_review = (
                self._classify_sparse_section(
                    slide,
                    text_blob=text_blob,
                    previous_slide=previous_slide,
                    next_slide=next_slide,
                )
            )
            evidence.extend(sparse_evidence)
            force_review = force_review or sparse_review
        else:
            functional = FunctionalSlideType.CONTENT
            confidence = 0.65
            evidence.append("default content page")

        # Content type refinement for content pages / unresolved content labels.
        if functional == FunctionalSlideType.CONTENT or content == ArchitecturalContentType.UNKNOWN:
            content, c_conf, c_ev = self._classify_content(slide, text_blob, lower)
            evidence.extend(c_ev)
            if functional == FunctionalSlideType.CONTENT and not force_review:
                confidence = min(0.95, (confidence + c_conf) / 2 + 0.1)
            elif functional == FunctionalSlideType.CONTENT and force_review:
                # Keep ambiguous sparse/prior cases reviewable — do not inflate confidence.
                confidence = min(confidence, 0.54)
                evidence.append(f"content_hint={content.value}")

        needs_review = (
            force_review
            or confidence < _LOW_CONFIDENCE
            or functional == FunctionalSlideType.UNKNOWN
        )
        if slide.parse_warnings:
            needs_review = True
            evidence.append("parse warnings present")
            confidence = min(confidence, 0.45)

        # Ambiguous forced-review paths stay below the open-review threshold.
        if force_review:
            confidence = min(confidence, 0.54)

        evidence.append("classifier=rule_driven_structural_v1")
        return FunctionalSlideClassification(
            slide_id=slide.slide_id,
            slide_index=slide.slide_index,
            functional_type=functional,
            content_type=content,
            confidence=round(confidence, 3),
            evidence=evidence,
            needs_review=needs_review,
        )

    def _apply_first_page_prior(
        self,
        slide: ReferenceSlideSnapshot,
        text_blob: str,
    ) -> tuple[
        FunctionalSlideType,
        ArchitecturalContentType,
        float,
        list[str],
        bool,
    ]:
        evidence = ["first-page prior"]
        # Dense first page → likely not a classic cover.
        dense = (
            len(slide.elements) >= 8
            or slide.text_length >= 180
            or slide.image_count >= 3
        )
        if dense:
            evidence.append("dense first page — prior weakened")
            return (
                FunctionalSlideType.CONTENT,
                ArchitecturalContentType.UNKNOWN,
                0.5,
                evidence,
                True,
            )
        # Classic sparse/title-heavy openers keep a moderate cover prior.
        title_like = any(e.semantic_role == "title" for e in slide.elements) or (
            slide.text_length > 0 and slide.text_length < 120
        )
        if title_like:
            evidence.append("title-like opener supports cover prior")
            return (
                FunctionalSlideType.COVER,
                ArchitecturalContentType.COVER_VISUAL,
                0.68,
                evidence,
                False,
            )
        evidence.append("weak cover signals — review recommended")
        return (
            FunctionalSlideType.COVER,
            ArchitecturalContentType.COVER_VISUAL,
            0.52,
            evidence,
            True,
        )

    def _is_sparse_candidate(self, slide: ReferenceSlideSnapshot) -> bool:
        return (
            slide.slide_index > 0
            and len(slide.text_content) <= 2
            and slide.image_count <= 1
            and slide.text_length < 80
        )

    def _classify_sparse_section(
        self,
        slide: ReferenceSlideSnapshot,
        *,
        text_blob: str,
        previous_slide: ReferenceSlideSnapshot | None,
        next_slide: ReferenceSlideSnapshot | None,
    ) -> tuple[
        FunctionalSlideType,
        ArchitecturalContentType,
        float,
        list[str],
        bool,
    ]:
        """Sparse pages are ambiguous — always open for review at V1."""
        evidence = ["sparse section candidate"]
        confidence = 0.5
        # Neighbor context can slightly raise confidence but does not close review.
        if previous_slide is not None and next_slide is not None:
            prev_dense = previous_slide.text_length >= 40 or previous_slide.image_count >= 1
            next_dense = next_slide.text_length >= 40 or next_slide.image_count >= 1
            if prev_dense and next_dense:
                confidence = 0.54
                evidence.append("neighbors look like content flanking a divider")
        if any(
            token in text_blob
            for token in ("章", "节", "部分", "Part ", "Chapter", "一、", "二、", "三、")
        ):
            confidence = max(confidence, 0.54)
            evidence.append("chapter-like wording")
        # Large single visual on a sparse page is often content, not a divider.
        if slide.image_count == 1 and any(
            e.element_type
            in {ReferenceElementType.IMAGE, ReferenceElementType.DRAWING}
            and e.width * e.height >= 8.0
            for e in slide.iter_elements()
        ):
            evidence.append("large visual — prefer content over section")
            return (
                FunctionalSlideType.CONTENT,
                ArchitecturalContentType.IMAGE_TEXT_HYBRID
                if slide.text_length > 0
                else ArchitecturalContentType.UNKNOWN,
                0.5,
                evidence,
                True,
            )
        return (
            FunctionalSlideType.SECTION_DIVIDER,
            ArchitecturalContentType.SECTION_VISUAL,
            confidence,
            evidence,
            True,  # always needs_review for sparse heuristic
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
            for e in slide.iter_elements()
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
        if any(e.semantic_role == "metric" for e in slide.iter_elements()) or sum(
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


def _has_disclaimer(text_blob: str, lower: str) -> bool:
    return any(token in text_blob or token in lower for token in _DISCLAIMER_TOKENS)
