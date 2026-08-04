"""Read-only Visual Critic — Visual Quality heuristics + optional LLM vision.

Never calls LayoutRepairService and never blocks formal PPTX export.
"""

from __future__ import annotations

import statistics
from collections import Counter
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, Field

from archium.application.visual.template_usage_brief_context import (
    TemplateUsageConstraints,
)
from archium.domain.visual.critic import (
    CRITIC_ALIGNMENT_DRIFT,
    CRITIC_BALANCE_OFF,
    CRITIC_COLOR_CHAOS,
    CRITIC_COPY_DENSITY_HIGH,
    CRITIC_FOCUS_UNCLEAR,
    CRITIC_HERO_WEAK,
    CRITIC_MECHANICAL,
    CRITIC_PAGE_REPETITION,
    CRITIC_READING_ORDER_AWKWARD,
    CRITIC_TEMPLATE_BRIEF_VIOLATION,
    CRITIC_TENSION_FLAT,
    CRITIC_TITLE_WEAK,
    CRITIC_VISUAL_NOISE_HIGH,
    CRITIC_WHITESPACE_WEAK,
    VisualCriticDimensions,
    VisualCriticFinding,
    VisualCriticReport,
)
from archium.domain.visual.enums import (
    ImageFit,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    LayoutIssueSeverity,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.style.presets import StyleContentPolicy
from archium.domain.visual.template_usage_brief import TemplateUsageBrief
from archium.infrastructure.layout.geometry import Rect
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.logging import get_logger

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]


_METHOD = "heuristic_v0"
_METHOD_SCREENSHOT = "screenshot_v1"
_METHOD_VISION = "vision_v1"
logger = get_logger(__name__, operation="visual_critic")

_VISION_SYSTEM = (
    "You are an architectural presentation Visual Critic. "
    "Evaluate ONLY visual quality of the slide screenshot. "
    "Do not invent layout repairs or silently rewrite the deck. "
    "Suggestions must be actionable percentages when possible "
    "(e.g. reduce copy ~30%, increase hero area ~20%). "
    "Return JSON only."
)

_TEXT_ROLES = frozenset(
    {
        LayoutElementRole.BODY_TEXT,
        LayoutElementRole.LEAD_STATEMENT,
        LayoutElementRole.CAPTION,
        LayoutElementRole.ANNOTATION,
    }
)


class _VisionFindingDraft(BaseModel):
    rule_code: str
    severity: str = "warning"
    message: str
    suggestion: str | None = None


class _VisionCriticDraft(BaseModel):
    focus_hierarchy_clarity: float = Field(ge=0.0, le=1.0)
    reading_order_naturalness: float = Field(ge=0.0, le=1.0)
    hero_prominence: float = Field(ge=0.0, le=1.0)
    color_chaos: float = Field(ge=0.0, le=1.0, description="1=calm palette, 0=chaotic")
    mechanical_feel: float = Field(ge=0.0, le=1.0, description="1=organic, 0=mechanical")
    findings: list[_VisionFindingDraft] = Field(default_factory=list)
    summary: str = ""


class VisualCriticService:
    """Evaluate Visual Quality — never calls LayoutRepairService."""

    def __init__(
        self,
        *,
        llm: LLMProvider | None = None,
        llm_enabled: bool = False,
        llm_model: str | None = None,
    ) -> None:
        self._llm = llm
        self._llm_enabled = llm_enabled
        self._llm_model = llm_model

    def evaluate_plan(
        self,
        plan: LayoutPlan,
        *,
        image_path: str | Path | None = None,
        page_area: float | None = None,
        peer_plans: list[LayoutPlan] | None = None,
        usage_brief: TemplateUsageBrief | None = None,
        usage_constraints: TemplateUsageConstraints | None = None,
        content_policy: StyleContentPolicy | None = None,
    ) -> VisualCriticReport:
        findings: list[VisualCriticFinding] = []
        notes: list[str] = []
        safe = Rect(0.0, 0.0, plan.page_width, plan.page_height)
        area = page_area or max(safe.area, 1e-6)

        focus = self._score_focus(plan, area)
        reading = self._score_reading_order(plan)
        hero = self._score_hero(plan, area)
        mechanical = self._score_mechanical(plan)
        balance = self._score_balance(plan, area)
        whitespace = self._score_whitespace(plan)
        alignment = self._score_alignment(plan)
        tension = self._score_tension(plan, area)
        visual_noise = self._score_visual_noise(plan)
        color = None
        repetition = self._score_repetition(plan, peer_plans or [])
        method = _METHOD

        if usage_brief is not None or usage_constraints is not None:
            findings.extend(
                self._findings_from_usage_brief(
                    plan, usage_brief=usage_brief, usage_constraints=usage_constraints
                )
            )
            if usage_brief is not None:
                notes.append(f"TemplateUsageBrief {usage_brief.id} v{usage_brief.version}")
            elif usage_constraints is not None:
                notes.append(
                    f"TemplateUsageBrief {usage_constraints.brief_id} "
                    f"v{usage_constraints.brief_version}"
                )

        if focus < 0.55:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_FOCUS_UNCLEAR,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Page visual focus / hierarchy looks unclear.",
                    suggestion=(
                        "Strengthen title/hero contrast (~20% clearer hierarchy) "
                        "or reduce competing equal-weight boxes."
                    ),
                    evidence={"focus_hierarchy_clarity": focus},
                )
            )
        if reading < 0.55:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_READING_ORDER_AWKWARD,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Reading order jumps against typical top-to-bottom flow.",
                    suggestion="Reorder or reposition elements to follow a natural scan path.",
                    evidence={"reading_order_naturalness": reading},
                )
            )
        if hero is not None and hero < 0.5:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_HERO_WEAK,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Hero visual does not dominate the page enough.",
                    suggestion=(
                        "Enlarge primary visual by ~20%; reduce competing "
                        "supporting visuals and text blocks."
                    ),
                    evidence={"hero_prominence": hero},
                )
            )
        if mechanical < 0.45:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_MECHANICAL,
                    severity=LayoutIssueSeverity.INFO,
                    message="Layout reads as mechanically regular / template-like.",
                    suggestion="Vary block sizes or introduce intentional asymmetry.",
                    evidence={"mechanical_feel": mechanical},
                )
            )
        if repetition is not None and repetition < 0.4:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_PAGE_REPETITION,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Page geometry closely repeats another slide in the deck.",
                    suggestion="Vary family/variant or supporting content across similar pages.",
                    evidence={"multi_page_repetition": repetition},
                )
            )
        if whitespace < 0.5:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_WHITESPACE_WEAK,
                    severity=LayoutIssueSeverity.INFO,
                    message="Whitespace control is weak; page reads either cramped or overly empty.",
                    suggestion=(
                        "Adjust copy/hero balance to recover breathing room "
                        "(target whitespace shift ~10-15%)."
                    ),
                    evidence={"whitespace": whitespace},
                )
            )
        if alignment < 0.55:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_ALIGNMENT_DRIFT,
                    severity=LayoutIssueSeverity.INFO,
                    message="Element edges drift without a clear alignment discipline.",
                    suggestion="Snap major boxes to 1-2 shared vertical edges; reduce small offsets.",
                    evidence={"alignment": alignment},
                )
            )
        if balance < 0.52:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_BALANCE_OFF,
                    severity=LayoutIssueSeverity.INFO,
                    message="Visual mass feels lopsided across the page.",
                    suggestion="Redistribute hero/text weight or counter-balance the heavy side by ~15%.",
                    evidence={"balance": balance},
                )
            )
        if visual_noise < 0.5:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_VISUAL_NOISE_HIGH,
                    severity=LayoutIssueSeverity.INFO,
                    message="Page carries too many small competing visual signals.",
                    suggestion="Remove low-value accents/icons and merge minor annotations (~20% fewer signals).",
                    evidence={"visual_noise": visual_noise},
                )
            )
        if tension < 0.45:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_TENSION_FLAT,
                    severity=LayoutIssueSeverity.INFO,
                    message="Scale contrast is too flat to create a strong editorial rhythm.",
                    suggestion="Increase contrast between primary and secondary elements (~20% scale gap).",
                    evidence={"tension": tension},
                )
            )

        structure = self._structure_findings(plan, area, content_policy=content_policy)
        if structure:
            findings.extend(structure)
            notes.append("screenshot_v1 structure pass (plan metrics; offline CI path).")

        # Promote method when v0.3 actionable visual findings are present
        # (structure codes or enhanced hero/focus suggestions).
        if any(
            item.rule_code
            in {
                CRITIC_TITLE_WEAK,
                CRITIC_COPY_DENSITY_HIGH,
                CRITIC_HERO_WEAK,
                CRITIC_FOCUS_UNCLEAR,
            }
            for item in findings
        ):
            method = _METHOD_SCREENSHOT

        source: str | None = None
        if image_path is not None:
            path = Path(image_path)
            if path.is_file():
                source = str(path)
                if method == _METHOD:
                    method = _METHOD_SCREENSHOT
                color = self._score_color_calm(path)
                if color is not None and color < 0.45:
                    findings.append(
                        VisualCriticFinding(
                            rule_code=CRITIC_COLOR_CHAOS,
                            severity=LayoutIssueSeverity.WARNING,
                            message="Screenshot palette looks noisy / over-saturated.",
                            suggestion=(
                                "Reduce accent variety; prefer restrained presentation colors."
                            ),
                            evidence={"color_calm": color},
                        )
                    )
                if self._llm_enabled and self._llm is not None:
                    vision = self._llm_vision_critique(plan, path)
                    if vision is not None:
                        method = _METHOD_VISION
                        focus = (focus + vision.focus_hierarchy_clarity) / 2
                        reading = (reading + vision.reading_order_naturalness) / 2
                        if hero is not None:
                            hero = (hero + vision.hero_prominence) / 2
                        mechanical = (mechanical + vision.mechanical_feel) / 2
                        color = (
                            vision.color_chaos
                            if color is None
                            else (color + vision.color_chaos) / 2
                        )
                        findings.extend(self._findings_from_vision(vision))
                        if vision.summary:
                            notes.append(f"LLM vision: {vision.summary[:240]}")
            else:
                notes.append(f"Screenshot not found: {path}")
        else:
            notes.append(
                "No screenshot provided; color_chaos skipped "
                "(structure/geometry critic still runs)."
            )

        dimensions = VisualCriticDimensions(
            focus_hierarchy_clarity=round(focus, 3),
            reading_order_naturalness=round(reading, 3),
            hero_prominence=None if hero is None else round(hero, 3),
            color_chaos=None if color is None else round(color, 3),
            mechanical_feel=round(mechanical, 3),
            multi_page_repetition=(None if repetition is None else round(repetition, 3)),
            balance=round(balance, 3),
            whitespace=round(whitespace, 3),
            tension=round(tension, 3),
            alignment=round(alignment, 3),
            visual_noise=round(visual_noise, 3),
        )
        return VisualCriticReport(
            score_kind="visual_quality",
            method=method,
            layout_plan_id=str(plan.id),
            slide_id=str(plan.slide_id),
            source_image=source,
            dimensions=dimensions,
            findings=self._dedupe_findings(findings),
            total_score=self._aggregate(dimensions),
            notes=notes,
        )

    def evaluate_deck(
        self,
        plans: list[LayoutPlan],
        *,
        image_paths: dict[str, str | Path] | None = None,
    ) -> list[VisualCriticReport]:
        paths = image_paths or {}
        reports: list[VisualCriticReport] = []
        for plan in plans:
            key = str(plan.id)
            reports.append(
                self.evaluate_plan(
                    plan,
                    image_path=paths.get(key) or paths.get(str(plan.slide_id)),
                    peer_plans=[p for p in plans if p.id != plan.id],
                )
            )
        return reports

    def _llm_vision_critique(self, plan: LayoutPlan, image_path: Path) -> _VisionCriticDraft | None:
        assert self._llm is not None
        prompt = (
            "Critique this architectural presentation slide screenshot.\n"
            f"LayoutFamily={plan.layout_family.value} variant={plan.layout_variant}.\n"
            "Score 0-1 for: focus_hierarchy_clarity, reading_order_naturalness, "
            "hero_prominence, color_chaos (1=calm), mechanical_feel (1=organic).\n"
            "Findings rule_code must be one of: "
            "CRITIC.FOCUS_UNCLEAR, CRITIC.READING_ORDER_AWKWARD, CRITIC.HERO_WEAK, "
            "CRITIC.COLOR_CHAOS, CRITIC.MECHANICAL, CRITIC.TITLE_WEAK, "
            "CRITIC.COPY_DENSITY_HIGH.\n"
            "Suggestions must be actionable with approximate percentages when useful "
            "(e.g. reduce copy ~30%, increase hero area ~20%).\n"
            "Return JSON matching the schema."
        )
        try:
            from archium.application.agent_skills import apply_skills_to_request

            request, skill_audit = apply_skills_to_request(
                LLMRequest(
                    system_prompt=_VISION_SYSTEM,
                    user_prompt=prompt,
                    model=self._llm_model,
                    temperature=0.2,
                    json_mode=True,
                    image_paths=(str(image_path),),
                    metadata={"task": "visual_critic_vision"},
                ),
                task_type="visual_qa",
                slide_type=str(getattr(plan, "layout_family", "") or ""),
                limit=4,
            )
            from archium.application.agent_skills.audit_store import record_skill_audit
            from archium.config.settings import get_settings

            record_skill_audit(skill_audit, settings=get_settings())
            return self._llm.generate_structured(request, _VisionCriticDraft)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM vision critic failed (non-fatal): %s", exc)
            return None

    @staticmethod
    def _findings_from_vision(draft: _VisionCriticDraft) -> list[VisualCriticFinding]:
        allowed = {
            CRITIC_FOCUS_UNCLEAR,
            CRITIC_READING_ORDER_AWKWARD,
            CRITIC_HERO_WEAK,
            CRITIC_COLOR_CHAOS,
            CRITIC_MECHANICAL,
            CRITIC_TITLE_WEAK,
            CRITIC_COPY_DENSITY_HIGH,
        }
        out: list[VisualCriticFinding] = []
        for item in draft.findings:
            code = item.rule_code.strip().upper().replace(" ", "_")
            if not code.startswith("CRITIC."):
                code = f"CRITIC.{code}" if "." not in code else code
            normalized = {
                "CRITIC.FOCUS_UNCLEAR": CRITIC_FOCUS_UNCLEAR,
                "CRITIC.READING_ORDER_AWKWARD": CRITIC_READING_ORDER_AWKWARD,
                "CRITIC.HERO_WEAK": CRITIC_HERO_WEAK,
                "CRITIC.COLOR_CHAOS": CRITIC_COLOR_CHAOS,
                "CRITIC.MECHANICAL": CRITIC_MECHANICAL,
                "CRITIC.TITLE_WEAK": CRITIC_TITLE_WEAK,
                "CRITIC.COPY_DENSITY_HIGH": CRITIC_COPY_DENSITY_HIGH,
            }.get(code, code)
            if normalized not in allowed:
                continue
            severity = LayoutIssueSeverity.WARNING
            if item.severity.lower() in {"info", "suggestion"}:
                severity = LayoutIssueSeverity.INFO
            out.append(
                VisualCriticFinding(
                    rule_code=normalized,
                    severity=severity,
                    message=item.message,
                    suggestion=item.suggestion,
                    evidence={"source": "llm_vision"},
                )
            )
        return out

    def _structure_findings(
        self,
        plan: LayoutPlan,
        page_area: float,
        *,
        content_policy: StyleContentPolicy | None = None,
    ) -> list[VisualCriticFinding]:
        """Deterministic screenshot-structure critic (plan metrics; CI-safe)."""
        findings: list[VisualCriticFinding] = []
        titles = plan.elements_by_role(LayoutElementRole.TITLE)
        if titles:
            title = max(titles, key=lambda item: item.area)
            height_ratio = title.height / max(plan.page_height, 1e-6)
            area_ratio = title.area / page_area
            if height_ratio < 0.06 or area_ratio < 0.028:
                findings.append(
                    VisualCriticFinding(
                        rule_code=CRITIC_TITLE_WEAK,
                        severity=LayoutIssueSeverity.WARNING,
                        message="Title is too weak to form a clear visual focus.",
                        suggestion=(
                            "Strengthen title: increase title band height ~25% "
                            "or raise contrast so the headline anchors the page."
                        ),
                        evidence={
                            "title_height_ratio": round(height_ratio, 4),
                            "title_area_ratio": round(area_ratio, 4),
                            "source": "screenshot_structure_v1",
                        },
                    )
                )

        copy_area = sum(
            el.area
            for el in plan.elements
            if el.role in _TEXT_ROLES
            or (
                el.content_type == LayoutContentType.TEXT
                and el.role
                not in {
                    LayoutElementRole.TITLE,
                    LayoutElementRole.FOOTER,
                    LayoutElementRole.DECORATION,
                }
            )
        )
        copy_ratio = copy_area / page_area
        copy_limit = 0.35
        if content_policy and content_policy.preferred_whitespace is not None:
            # Higher whitespace preference → lower allowed copy area.
            copy_limit = max(0.18, 0.50 - content_policy.preferred_whitespace)
        if copy_ratio > copy_limit:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_COPY_DENSITY_HIGH,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Body copy density is too high for architectural presentation.",
                    suggestion=(
                        "Reduce body copy by ~30%; keep a single conclusion bar "
                        "and let the primary visual breathe."
                    ),
                    evidence={
                        "copy_area_ratio": round(copy_ratio, 4),
                        "copy_limit": round(copy_limit, 4),
                        "source": "screenshot_structure_v1",
                    },
                )
            )

        if content_policy is not None:
            image_count = sum(
                1
                for el in plan.elements
                if el.content_type == LayoutContentType.IMAGE
                and el.role
                in {
                    LayoutElementRole.HERO_VISUAL,
                    LayoutElementRole.SUPPORTING_VISUAL,
                }
            )
            diagram_count = sum(
                1 for el in plan.elements if el.content_type == LayoutContentType.DRAWING
            )
            if image_count > content_policy.max_images:
                findings.append(
                    VisualCriticFinding(
                        rule_code=CRITIC_COPY_DENSITY_HIGH,
                        severity=LayoutIssueSeverity.WARNING,
                        message=(
                            f"Too many images ({image_count}) for StylePreset "
                            f"content_policy max_images={content_policy.max_images}."
                        ),
                        suggestion=(
                            f"Keep ≤{content_policy.max_images} images; prefer one dominant visual."
                        ),
                        evidence={
                            "image_count": image_count,
                            "max_images": content_policy.max_images,
                            "source": "style_content_policy",
                        },
                    )
                )
            if diagram_count > content_policy.max_diagrams:
                findings.append(
                    VisualCriticFinding(
                        rule_code=CRITIC_COPY_DENSITY_HIGH,
                        severity=LayoutIssueSeverity.INFO,
                        message=(
                            f"Too many diagrams ({diagram_count}) for StylePreset "
                            f"max_diagrams={content_policy.max_diagrams}."
                        ),
                        suggestion=(
                            f"Keep ≤{content_policy.max_diagrams} drawings; "
                            "split across pages if needed."
                        ),
                        evidence={
                            "diagram_count": diagram_count,
                            "max_diagrams": content_policy.max_diagrams,
                            "source": "style_content_policy",
                        },
                    )
                )
        return findings

    @staticmethod
    def _dedupe_findings(findings: list[VisualCriticFinding]) -> list[VisualCriticFinding]:
        seen: set[str] = set()
        out: list[VisualCriticFinding] = []
        for item in findings:
            if item.rule_code in seen:
                continue
            seen.add(item.rule_code)
            out.append(item)
        return out

    @staticmethod
    def _aggregate(dimensions: VisualCriticDimensions) -> float | None:
        values = [
            value
            for value in (
                dimensions.focus_hierarchy_clarity,
                dimensions.reading_order_naturalness,
                dimensions.hero_prominence,
                dimensions.color_chaos,
                dimensions.mechanical_feel,
                dimensions.multi_page_repetition,
                dimensions.balance,
                dimensions.whitespace,
                dimensions.tension,
                dimensions.alignment,
                dimensions.visual_noise,
            )
            if value is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    def _score_focus(self, plan: LayoutPlan, page_area: float) -> float:
        areas = sorted((el.area for el in plan.elements), reverse=True)
        if not areas:
            return 0.2
        top = areas[0]
        second = areas[1] if len(areas) > 1 else 0.0
        dominance = top / page_area
        gap = (top - second) / max(top, 1e-6)
        has_title = bool(plan.elements_by_role(LayoutElementRole.TITLE))
        score = 0.45 * min(1.0, dominance * 2.2) + 0.35 * gap + (0.2 if has_title else 0.0)
        return max(0.0, min(1.0, score))

    def _score_reading_order(self, plan: LayoutPlan) -> float:
        by_id = {el.id: el for el in plan.elements}
        ordered: list[LayoutElement] = []
        for element_id in plan.reading_order:
            element = by_id.get(element_id)
            if element is not None:
                ordered.append(element)
        if len(ordered) < 2:
            return 1.0
        inversions = 0
        pairs = 0
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                pairs += 1
                if left.y - right.y > 0.35 or (
                    abs(left.y - right.y) <= 0.15 and left.x - right.x > 0.5
                ):
                    inversions += 1
        if pairs == 0:
            return 1.0
        return max(0.0, 1.0 - inversions / pairs)

    def _score_hero(self, plan: LayoutPlan, page_area: float) -> float | None:
        hero = None
        if plan.hero_element_id:
            hero = plan.element_by_id(plan.hero_element_id)
        if hero is None:
            heroes = plan.elements_by_role(LayoutElementRole.HERO_VISUAL)
            hero = heroes[0] if heroes else None
        if hero is None:
            return None
        ratio = hero.area / page_area
        return max(0.0, min(1.0, (ratio - 0.08) / 0.42))

    def _score_mechanical(self, plan: LayoutPlan) -> float:
        boxes = [el for el in plan.elements if el.role != LayoutElementRole.DECORATION]
        if len(boxes) < 3:
            return 0.85
        widths = [round(el.width, 2) for el in boxes]
        heights = [round(el.height, 2) for el in boxes]
        tops = [round(el.y, 2) for el in boxes]
        width_mode = Counter(widths).most_common(1)[0][1] / len(widths)
        height_mode = Counter(heights).most_common(1)[0][1] / len(heights)
        top_mode = Counter(tops).most_common(1)[0][1] / len(tops)
        regularity = (width_mode + height_mode + top_mode) / 3.0
        return max(0.0, min(1.0, 1.0 - regularity))

    def _score_balance(self, plan: LayoutPlan, page_area: float) -> float:
        if not plan.elements:
            return 0.2
        # Left-led monument / sparse text openers are intentional editorial asymmetry.
        if plan.layout_variant == "monument" or (
            plan.layout_variant == "lead_and_points"
            and len([el for el in plan.elements if el.role != LayoutElementRole.DECORATION]) <= 2
        ):
            return 0.72
        center_x = plan.page_width / 2.0
        left = 0.0
        right = 0.0
        for el in plan.elements:
            mass = el.area / max(page_area, 1e-6)
            if el.x + el.width / 2.0 <= center_x:
                left += mass
            else:
                right += mass
        total = max(left + right, 1e-6)
        delta = abs(left - right) / total
        return max(0.0, min(1.0, 1.0 - delta * 1.35))

    def _score_whitespace(self, plan: LayoutPlan) -> float:
        ratio = float(getattr(plan, "whitespace_ratio", 0.0) or 0.0)
        if ratio <= 0.0:
            return 0.45
        # Spacious text covers / sparse section openers keep more empty field.
        sparse_opener = plan.layout_variant == "monument" or (
            plan.layout_variant == "lead_and_points"
            and len([el for el in plan.elements if el.role != LayoutElementRole.DECORATION]) <= 2
        )
        target = 0.68 if sparse_opener else 0.22
        tolerance = 0.32 if sparse_opener else 0.22
        delta = abs(ratio - target)
        return max(0.0, min(1.0, 1.0 - delta / tolerance))

    def _score_alignment(self, plan: LayoutPlan) -> float:
        boxes = [el for el in plan.elements if el.role != LayoutElementRole.DECORATION]
        if len(boxes) < 2:
            return 0.9
        lefts = [round(el.x, 1) for el in boxes]
        rights = [round(el.x + el.width, 1) for el in boxes]
        tops = [round(el.y, 1) for el in boxes]
        left_mode = Counter(lefts).most_common(1)[0][1] / len(lefts)
        right_mode = Counter(rights).most_common(1)[0][1] / len(rights)
        top_mode = Counter(tops).most_common(1)[0][1] / len(tops)
        return max(0.0, min(1.0, (left_mode + right_mode + top_mode) / 3.0))

    def _score_tension(self, plan: LayoutPlan, page_area: float) -> float:
        areas = sorted((el.area / max(page_area, 1e-6) for el in plan.elements), reverse=True)
        if len(areas) < 2:
            return 0.4
        gap = areas[0] - areas[1]
        return max(0.0, min(1.0, gap / 0.22))

    def _score_visual_noise(self, plan: LayoutPlan) -> float:
        content = [el for el in plan.elements if el.role != LayoutElementRole.DECORATION]
        if not content:
            return 0.2
        tiny = sum(1 for el in content if el.area < 0.35)
        annotations = sum(
            1
            for el in content
            if el.role in {LayoutElementRole.CAPTION, LayoutElementRole.ANNOTATION}
        )
        noise = (tiny + annotations) / max(len(content), 1)
        return max(0.0, min(1.0, 1.0 - noise * 0.75))

    def _score_repetition(self, plan: LayoutPlan, peers: list[LayoutPlan]) -> float | None:
        if not peers:
            return None
        fingerprint = self._geometry_fingerprint(plan)
        best = 0.0
        for peer in peers:
            if peer.id == plan.id:
                continue
            best = max(
                best,
                self._fingerprint_similarity(fingerprint, self._geometry_fingerprint(peer)),
            )
        return max(0.0, min(1.0, 1.0 - best))

    @staticmethod
    def _geometry_fingerprint(
        plan: LayoutPlan,
    ) -> list[tuple[str, float, float, float, float]]:
        return [
            (
                el.role.value,
                round(el.x, 2),
                round(el.y, 2),
                round(el.width, 2),
                round(el.height, 2),
            )
            for el in sorted(plan.elements, key=lambda item: item.id)
        ]

    def _findings_from_usage_brief(
        self,
        plan: LayoutPlan,
        *,
        usage_brief: TemplateUsageBrief | None = None,
        usage_constraints: TemplateUsageConstraints | None = None,
    ) -> list[VisualCriticFinding]:
        from archium.application.visual.template_usage_brief_context import (
            constraints_from_brief,
        )

        constraints = usage_constraints
        if constraints is None and usage_brief is not None:
            constraints = constraints_from_brief(usage_brief)
        if constraints is None:
            return []
        findings: list[VisualCriticFinding] = []
        if constraints.forbid_drawing_cover_crop:
            for element in plan.elements:
                if element.role not in {
                    LayoutElementRole.HERO_VISUAL,
                    LayoutElementRole.SUPPORTING_VISUAL,
                }:
                    continue
                fit = element.fit_mode
                # Drawing-focus pages must not use cover when brief forbids it.
                if (
                    fit is not None
                    and fit != ImageFit.CONTAIN
                    and (
                        plan.layout_family == LayoutFamily.DRAWING_FOCUS
                        or element.content_type == LayoutContentType.DRAWING
                    )
                ):
                    findings.append(
                        VisualCriticFinding(
                            rule_code=CRITIC_TEMPLATE_BRIEF_VIOLATION,
                            severity=LayoutIssueSeverity.ERROR,
                            message=(
                                f"Element `{element.id}` fit={fit.value} violates "
                                f"TemplateUsageBrief v{constraints.brief_version} "
                                "drawing contain rule."
                            ),
                            suggestion="Set drawing fit_mode=contain; forbid cover/crop.",
                            evidence={
                                "template_usage_brief_id": str(constraints.brief_id),
                                "template_usage_brief_version": constraints.brief_version,
                                "element_id": element.id,
                            },
                        )
                    )
        return findings

    @staticmethod
    def _fingerprint_similarity(left: list[tuple[Any, ...]], right: list[tuple[Any, ...]]) -> float:
        if not left or not right:
            return 0.0
        roles_l = [item[0] for item in left]
        roles_r = [item[0] for item in right]
        if roles_l != roles_r:
            shared = len(set(roles_l) & set(roles_r))
            role_score = shared / max(len(set(roles_l) | set(roles_r)), 1)
            return role_score * 0.35
        deltas: list[float] = []
        for a, b in zip(left, right, strict=False):
            deltas.append(abs(a[1] - b[1]) + abs(a[2] - b[2]) + abs(a[3] - b[3]) + abs(a[4] - b[4]))
        mean_delta = statistics.fmean(deltas) if deltas else 0.0
        return max(0.0, min(1.0, 1.0 - mean_delta / 4.0))

    def _score_color_calm(self, path: Path) -> float | None:
        if Image is None:
            return None
        try:
            with Image.open(path) as image:
                rgb = image.convert("RGB")
                rgb.thumbnail((160, 90))
                pixels: list[tuple[int, int, int]]
                if hasattr(rgb, "get_flattened_data"):
                    pixels = cast(list[tuple[int, int, int]], list(rgb.get_flattened_data()))
                else:
                    pixels = list(rgb.getdata())
        except OSError:
            return None
        if not pixels:
            return None
        buckets = Counter(((r // 32), (g // 32), (b // 32)) for r, g, b in pixels)
        unique = len(buckets)
        sats: list[float] = []
        for r, g, b in pixels[:: max(1, len(pixels) // 200)]:
            mx = max(r, g, b)
            mn = min(r, g, b)
            sats.append(0.0 if mx == 0 else (mx - mn) / mx)
        sat_mean = statistics.fmean(sats) if sats else 0.0
        diversity_penalty = min(1.0, unique / 48.0)
        sat_penalty = min(1.0, sat_mean / 0.65)
        chaos = 0.6 * diversity_penalty + 0.4 * sat_penalty
        return max(0.0, min(1.0, 1.0 - chaos))
