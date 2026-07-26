"""Design Corpus service — seed + match annotated presentation pages."""

from __future__ import annotations

import json
from pathlib import Path

from archium.domain.visual.design_corpus import DesignCorpusPage
from archium.domain.visual.page_visual_grammar import (
    PageVisualFormula,
    list_page_formulas,
    select_page_formula,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CASE_001_OUTLINE = (
    _REPO_ROOT / "scripts" / "showcase" / "case_001_hospital" / "outline.json"
)

# Continuity role → emotion for formula selection on Case 001 seeds.
_ROLE_EMOTION: dict[str, str] = {
    "opening": "climax",
    "explanation": "calm",
    "evidence": "problem",
    "analysis": "calm",
    "strategy": "strategy",
    "climax": "climax",
    "decision": "decision",
    "closing": "calm",
}

_FORMULA_PAGE_TYPE: dict[str, str] = {
    "problem_evidence_conflict": "problem",
    "strategy_existing_transform": "strategy",
    "before_after_cut": "strategy",
    "process_sequence": "process",
    "drawing_dominant": "drawing",
    "hero_statement": "cover",
    "monument_image": "climax",
    "layer_analysis": "analysis",
    "path_experience": "circulation",
    "core_expansion": "concept",
    "decision_metric": "decision",
    "quiet_argument": "conclusion",
    "section_opener": "section",
    "phasing_timeline": "phasing",
    "threshold_sequence": "experience",
    "evidence_triptych": "evidence",
    "axonometric_callout": "drawing",
    "masterplan_focus": "masterplan",
    "program_stack": "program",
    "quote_citation": "quote",
}

_FORMULA_PATTERN: dict[str, str] = {
    "problem_evidence_conflict": "photo_plus_analysis",
    "strategy_existing_transform": "diagram_first",
    "before_after_cut": "before_after",
    "process_sequence": "timeline_axis",
    "drawing_dominant": "drawing_first",
    "hero_statement": "hero_full",
    "monument_image": "monument",
    "layer_analysis": "layered_base",
    "path_experience": "path_nodes",
    "core_expansion": "radial_growth",
    "decision_metric": "metric_caption",
    "quiet_argument": "whitespace_claim",
    "section_opener": "section_index",
    "phasing_timeline": "timeline_axis",
    "threshold_sequence": "path_nodes",
    "evidence_triptych": "photo_triptych",
    "axonometric_callout": "drawing_callout",
    "masterplan_focus": "masterplan",
    "program_stack": "stack_diagram",
    "quote_citation": "quote_whitespace",
}

_FORMULA_DOMINANT: dict[str, str] = {
    "problem_evidence_conflict": "photo",
    "strategy_existing_transform": "diagram",
    "before_after_cut": "photo",
    "process_sequence": "diagram",
    "drawing_dominant": "drawing",
    "hero_statement": "image",
    "monument_image": "image",
    "layer_analysis": "drawing",
    "path_experience": "diagram",
    "core_expansion": "diagram",
    "decision_metric": "text",
    "quiet_argument": "text",
    "section_opener": "text",
    "phasing_timeline": "diagram",
    "threshold_sequence": "diagram",
    "evidence_triptych": "photo",
    "axonometric_callout": "drawing",
    "masterplan_focus": "drawing",
    "program_stack": "diagram",
    "quote_citation": "text",
}

_FORMULA_IMAGE_RATIO: dict[str, float] = {
    "hero_statement": 0.78,
    "monument_image": 0.85,
    "drawing_dominant": 0.72,
    "masterplan_focus": 0.75,
    "axonometric_callout": 0.7,
    "layer_analysis": 0.68,
    "path_experience": 0.62,
    "before_after_cut": 0.7,
    "evidence_triptych": 0.66,
    "quiet_argument": 0.15,
    "quote_citation": 0.1,
    "decision_metric": 0.25,
    "section_opener": 0.2,
}


class DesignCorpusService:
    """Load / synthesize Design Corpus pages for rhetoric matching."""

    def __init__(self, *, case_001_outline: Path | None = None) -> None:
        self._outline_path = case_001_outline or _CASE_001_OUTLINE
        self._cache: list[DesignCorpusPage] | None = None

    def list_pages(self, *, refresh: bool = False) -> list[DesignCorpusPage]:
        if self._cache is not None and not refresh:
            return list(self._cache)
        pages: list[DesignCorpusPage] = []
        pages.extend(self._formula_exemplars())
        pages.extend(self._case_001_pages())
        self._cache = pages
        return list(pages)

    def progress(self) -> dict[str, object]:
        pages = self.list_pages()
        by_source: dict[str, int] = {}
        by_formula: dict[str, int] = {}
        for page in pages:
            by_source[page.source] = by_source.get(page.source, 0) + 1
            if page.formula_id:
                by_formula[page.formula_id] = by_formula.get(page.formula_id, 0) + 1
        return {
            "total": len(pages),
            "target_v1": 50,
            "meets_v1_target": len(pages) >= 50,
            "by_source": by_source,
            "formula_coverage": len(by_formula),
            "formula_catalog_size": len(list_page_formulas()),
        }

    def match(
        self,
        *,
        formula_id: str | None = None,
        page_type: str | None = None,
        metaphor: str | None = None,
        limit: int = 5,
    ) -> list[DesignCorpusPage]:
        """Return nearest labeled pages for director / Studio hints."""
        scored: list[tuple[int, DesignCorpusPage]] = []
        for page in self.list_pages():
            score = 0
            if formula_id and page.formula_id == formula_id:
                score += 3
            if page_type and page.page_type == page_type:
                score += 2
            if metaphor and page.metaphor == metaphor:
                score += 2
            if score <= 0:
                continue
            scored.append((score, page))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [page for _, page in scored[:limit]]

    def _formula_exemplars(self) -> list[DesignCorpusPage]:
        pages: list[DesignCorpusPage] = []
        styles = ("architecture_technical", "minimal_architecture")
        for formula in list_page_formulas():
            for style in styles:
                pages.append(self._from_formula(formula, style=style))
        return pages

    def _from_formula(
        self, formula: PageVisualFormula, *, style: str
    ) -> DesignCorpusPage:
        fid = formula.id.value
        image_ratio = _FORMULA_IMAGE_RATIO.get(fid, 0.55)
        text_density = max(0.08, min(0.45, 0.55 - image_ratio * 0.45))
        if style == "minimal_architecture":
            text_density = max(0.06, text_density - 0.05)
            image_ratio = min(0.9, image_ratio + 0.04)
        return DesignCorpusPage(
            id=f"formula:{fid}:{style}",
            source="formula_exemplar",
            page_type=_FORMULA_PAGE_TYPE.get(fid, "content"),
            visual_pattern=_FORMULA_PATTERN.get(fid, "diagram_first"),
            image_ratio=round(image_ratio, 2),
            text_density=round(text_density, 2),
            dominant_element=_FORMULA_DOMINANT.get(fid, "diagram"),
            style=style,
            metaphor=None,
            formula_id=fid,
            title=formula.display_name,
            claim=f"{formula.display_name} — {' · '.join(formula.semantic_slots[:3])}",
        )

    def _case_001_pages(self) -> list[DesignCorpusPage]:
        if not self._outline_path.is_file():
            return []
        payload = json.loads(self._outline_path.read_text(encoding="utf-8"))
        slides = payload.get("slides") or []
        pages: list[DesignCorpusPage] = []
        for index, row in enumerate(slides):
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or f"slide_{index + 1}")
            role = str(row.get("continuity_role") or "explanation")
            emotion = _ROLE_EMOTION.get(role, "calm")
            formula = select_page_formula(emotion=emotion, title=title)
            fid = formula.id.value
            image_ratio = _FORMULA_IMAGE_RATIO.get(fid, 0.55)
            text_density = max(0.08, min(0.4, 0.5 - image_ratio * 0.4))
            pages.append(
                DesignCorpusPage(
                    id=f"case_001:{index + 1:02d}:{title}",
                    source="case_001_hospital",
                    page_type=_FORMULA_PAGE_TYPE.get(fid, "content"),
                    visual_pattern=_FORMULA_PATTERN.get(fid, "diagram_first"),
                    image_ratio=round(image_ratio, 2),
                    text_density=round(text_density, 2),
                    dominant_element=_FORMULA_DOMINANT.get(fid, "diagram"),
                    style="architecture_technical",
                    metaphor=None,
                    formula_id=fid,
                    title=title,
                    claim=str(row.get("message") or "")[:280] or None,
                )
            )
        return pages
