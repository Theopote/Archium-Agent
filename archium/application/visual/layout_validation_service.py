"""Layout validation service — geometric and semantic rule checks."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.asset_reference import AssetReferenceContext
from archium.domain.visual.design_system import DesignSystem, LayoutThresholds, TypographySystem
from archium.domain.visual.enums import (
    CropPolicy,
    ImageFit,
    LayoutContentType,
    LayoutElementRole,
    LayoutIssueSeverity,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.text_style import resolve_text_style, role_min_font_pt
from archium.domain.visual.validation import (
    LAYOUT_DRAWING_CROPPED,
    LAYOUT_ELEMENT_OUTSIDE_PAGE,
    LAYOUT_ELEMENT_OUTSIDE_SAFE_AREA,
    LAYOUT_ELEMENT_OVERLAP,
    LAYOUT_EXCESSIVE_DENSITY,
    LAYOUT_FONT_TOO_SMALL,
    LAYOUT_HERO_ASSET_MISSING,
    LAYOUT_HERO_NOT_DOMINANT,
    LAYOUT_IMAGE_DISTORTION,
    LAYOUT_INCONSISTENT_ALIGNMENT,
    LAYOUT_INSUFFICIENT_WHITESPACE,
    LAYOUT_INVALID_SIZE,
    LAYOUT_MISSING_ASSET_REFERENCE,
    LAYOUT_MISSING_SOURCE,
    LAYOUT_MISSING_TITLE,
    LAYOUT_TEXT_OVERFLOW,
    LAYOUT_UNRESOLVED_ASSET_PATH,
    LayoutScore,
    LayoutValidationIssue,
    LayoutValidationReport,
)
from archium.infrastructure.layout.geometry import Rect, safe_area
from archium.infrastructure.layout.text_measurement import TextMeasurementService

_ASSET_CONTENT_TYPES = frozenset(
    {
        LayoutContentType.IMAGE,
        LayoutContentType.DRAWING,
        LayoutContentType.CHART,
    }
)


class LayoutValidationService:
    """Validate LayoutPlan against DesignSystem thresholds and composition rules."""

    def __init__(self, text_measurement: TextMeasurementService | None = None) -> None:
        self._text = text_measurement or TextMeasurementService()

    def validate(
        self,
        layout_plan: LayoutPlan,
        design_system: DesignSystem,
        *,
        require_source: bool = True,
        drawing_hero: bool = False,
        asset_context: AssetReferenceContext | None = None,
    ) -> LayoutValidationReport:
        issues: list[LayoutValidationIssue] = []
        page = Rect(0, 0, layout_plan.page_width, layout_plan.page_height)
        safe = safe_area(design_system)
        thresholds = design_system.thresholds

        issues.extend(self._check_sizes(layout_plan))
        issues.extend(self._check_bounds(layout_plan, page, safe, design_system))
        issues.extend(self._check_overlaps(layout_plan, thresholds.max_overlap_tolerance))
        issues.extend(self._check_required_roles(layout_plan, require_source=require_source))
        issues.extend(self._check_typography(layout_plan, design_system.typography, thresholds))
        issues.extend(self._check_text_overflow(layout_plan, design_system.typography))
        issues.extend(self._check_image_rules(layout_plan, drawing_hero=drawing_hero))
        issues.extend(self._check_hero_dominance(layout_plan, safe, thresholds.min_hero_area_ratio))
        issues.extend(
            self._check_whitespace(
                layout_plan,
                thresholds.min_whitespace_ratio,
                thresholds.max_whitespace_ratio,
            )
        )
        issues.extend(self._check_alignment(layout_plan))
        if asset_context is not None:
            issues.extend(self._check_asset_references(layout_plan, asset_context))

        score = self._score(layout_plan, issues)
        return LayoutValidationReport(
            issues=issues,
            score=score.total_score,
            layout_score=score,
        )

    def _check_asset_references(
        self,
        plan: LayoutPlan,
        asset_context: AssetReferenceContext,
    ) -> list[LayoutValidationIssue]:
        """Validate content_ref integrity against known assets and resolvable paths."""
        issues: list[LayoutValidationIssue] = []
        known = asset_context.known_asset_ids
        resolved = asset_context.resolved_paths

        for element in plan.elements:
            if element.content_type not in _ASSET_CONTENT_TYPES:
                continue
            is_hero = self._is_hero_element(plan, element)
            severity = (
                LayoutIssueSeverity.ERROR if is_hero else LayoutIssueSeverity.WARNING
            )

            if not element.content_ref:
                if is_hero:
                    issues.append(
                        LayoutValidationIssue(
                            rule_code=LAYOUT_HERO_ASSET_MISSING,
                            severity=LayoutIssueSeverity.ERROR,
                            element_ids=[element.id],
                            message=f"Hero element {element.id} has no asset content_ref.",
                            suggestion="Bind a project asset to the hero visual.",
                            auto_repairable=False,
                        )
                    )
                else:
                    issues.append(
                        LayoutValidationIssue(
                            rule_code=LAYOUT_MISSING_ASSET_REFERENCE,
                            severity=LayoutIssueSeverity.WARNING,
                            element_ids=[element.id],
                            message=(
                                f"Element {element.id} expects an asset but "
                                "content_ref is empty."
                            ),
                            suggestion="Bind a supporting asset or remove the visual slot.",
                            auto_repairable=False,
                        )
                    )
                continue

            ref = element.content_ref
            missing = ref not in known
            path = resolved.get(ref)
            unresolved = (not missing) and (
                path is None or not Path(str(path)).is_file()
            )

            if missing:
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_MISSING_ASSET_REFERENCE,
                        severity=severity,
                        element_ids=[element.id],
                        message=(
                            f"Element {element.id} content_ref {ref[:8]}… "
                            "does not match a project asset."
                        ),
                        suggestion="Re-bind the element to an existing project asset.",
                        auto_repairable=False,
                    )
                )
                if is_hero:
                    issues.append(
                        LayoutValidationIssue(
                            rule_code=LAYOUT_HERO_ASSET_MISSING,
                            severity=LayoutIssueSeverity.ERROR,
                            element_ids=[element.id],
                            message=f"Hero asset for {element.id} is missing from the project.",
                            suggestion="Upload or select a valid hero asset.",
                            auto_repairable=False,
                        )
                    )
                continue

            if unresolved:
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_UNRESOLVED_ASSET_PATH,
                        severity=severity,
                        element_ids=[element.id],
                        message=(
                            f"Element {element.id} asset {ref[:8]}… "
                            "exists but its file path could not be resolved."
                        ),
                        suggestion="Restore the asset file or re-import the asset.",
                        auto_repairable=False,
                    )
                )
                if is_hero:
                    issues.append(
                        LayoutValidationIssue(
                            rule_code=LAYOUT_HERO_ASSET_MISSING,
                            severity=LayoutIssueSeverity.ERROR,
                            element_ids=[element.id],
                            message=(
                                f"Hero asset for {element.id} cannot be loaded from storage."
                            ),
                            suggestion="Fix the hero asset file path before export.",
                            auto_repairable=False,
                        )
                    )

        return issues

    @staticmethod
    def _is_hero_element(plan: LayoutPlan, element: LayoutElement) -> bool:
        if plan.hero_element_id is not None and element.id == plan.hero_element_id:
            return True
        return element.role == LayoutElementRole.HERO_VISUAL

    def _check_sizes(self, plan: LayoutPlan) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        for element in plan.elements:
            if element.width <= 0 or element.height <= 0:
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_INVALID_SIZE,
                        severity=LayoutIssueSeverity.CRITICAL,
                        element_ids=[element.id],
                        message=f"Element {element.id} has invalid size.",
                        suggestion="Ensure width and height are positive.",
                        auto_repairable=False,
                    )
                )
        return issues

    def _check_bounds(
        self,
        plan: LayoutPlan,
        page: Rect,
        safe: Rect,
        design_system: DesignSystem,
    ) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        for element in plan.elements:
            rect = Rect(element.x, element.y, element.width, element.height)
            if (
                rect.x < -1e-6
                or rect.y < -1e-6
                or rect.right > page.width + 1e-6
                or rect.bottom > page.height + 1e-6
            ):
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_ELEMENT_OUTSIDE_PAGE,
                        severity=LayoutIssueSeverity.CRITICAL,
                        element_ids=[element.id],
                        message=f"Element {element.id} extends outside the page.",
                        suggestion="Move the element back within page bounds.",
                        auto_repairable=True,
                    )
                )
            elif (
                design_system.page.safe_area_enabled
                and (
                    rect.x < safe.x - 1e-6
                    or rect.y < safe.y - 1e-6
                    or rect.right > safe.right + 1e-6
                    or rect.bottom > safe.bottom + 1e-6
                )
                and element.role
                not in {
                    LayoutElementRole.SOURCE,
                    LayoutElementRole.FOOTER,
                    LayoutElementRole.PAGE_NUMBER,
                }
            ):
                # Footer/source may sit in bottom margin strip.
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_ELEMENT_OUTSIDE_SAFE_AREA,
                        severity=LayoutIssueSeverity.ERROR,
                        element_ids=[element.id],
                        message=f"Element {element.id} is outside the safe area.",
                        suggestion="Move the element into the safe content area.",
                        auto_repairable=True,
                    )
                )
        return issues

    def _check_overlaps(
        self, plan: LayoutPlan, tolerance: float
    ) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        elements = plan.elements
        for i, left in enumerate(elements):
            if left.role == LayoutElementRole.DECORATION:
                continue
            left_rect = Rect(left.x, left.y, left.width, left.height)
            for right in elements[i + 1 :]:
                if right.role == LayoutElementRole.DECORATION:
                    continue
                # Overlay hero + lead is intentional for hero-overlay variant.
                if {left.role, right.role} == {
                    LayoutElementRole.HERO_VISUAL,
                    LayoutElementRole.LEAD_STATEMENT,
                }:
                    continue
                right_rect = Rect(right.x, right.y, right.width, right.height)
                if left_rect.overlaps(right_rect, tolerance=tolerance):
                    issues.append(
                        LayoutValidationIssue(
                            rule_code=LAYOUT_ELEMENT_OVERLAP,
                            severity=LayoutIssueSeverity.ERROR,
                            element_ids=[left.id, right.id],
                            message=f"Elements {left.id} and {right.id} overlap.",
                            suggestion="Increase spacing or resize elements.",
                            auto_repairable=True,
                        )
                    )
        return issues

    def _check_required_roles(
        self, plan: LayoutPlan, *, require_source: bool
    ) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        if not plan.elements_by_role(LayoutElementRole.TITLE):
            issues.append(
                LayoutValidationIssue(
                    rule_code=LAYOUT_MISSING_TITLE,
                    severity=LayoutIssueSeverity.ERROR,
                    element_ids=[],
                    message="Layout is missing a title element.",
                    suggestion="Add a title element.",
                    auto_repairable=False,
                )
            )
        if require_source and not plan.elements_by_role(LayoutElementRole.SOURCE):
            issues.append(
                LayoutValidationIssue(
                    rule_code=LAYOUT_MISSING_SOURCE,
                    severity=LayoutIssueSeverity.WARNING,
                    element_ids=[],
                    message="Layout is missing a visible source element.",
                    suggestion="Add a source citation on the page.",
                    auto_repairable=False,
                )
            )
        return issues

    def _check_typography(
        self,
        plan: LayoutPlan,
        typography: TypographySystem,
        thresholds: LayoutThresholds,
    ) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        for element in plan.elements:
            if element.content_type != LayoutContentType.TEXT and element.role not in {
                LayoutElementRole.TITLE,
                LayoutElementRole.BODY_TEXT,
                LayoutElementRole.CAPTION,
                LayoutElementRole.SOURCE,
                LayoutElementRole.LEAD_STATEMENT,
            }:
                continue
            style = resolve_text_style(element, typography)
            minimum = role_min_font_pt(element.role, thresholds)
            if style.font_size + 1e-6 < minimum:
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_FONT_TOO_SMALL,
                        severity=LayoutIssueSeverity.ERROR,
                        element_ids=[element.id],
                        message=f"Font size for {element.id} is below minimum ({minimum} pt).",
                        suggestion="Increase font size or use a larger style token.",
                        auto_repairable=True,
                    )
                )
        return issues

    def _check_text_overflow(
        self, plan: LayoutPlan, typography: TypographySystem
    ) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        for element in plan.elements:
            if not element.text_content:
                continue
            if element.content_type not in {
                LayoutContentType.TEXT,
                LayoutContentType.METRIC,
            }:
                continue
            style = resolve_text_style(element, typography)
            if not self._text.fits(
                element.text_content,
                box_width_in=element.width,
                box_height_in=element.height,
                style=style,
            ):
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_TEXT_OVERFLOW,
                        severity=LayoutIssueSeverity.ERROR,
                        element_ids=[element.id],
                        message=f"Text in {element.id} overflows its box.",
                        suggestion="Enlarge the text box or shorten the copy.",
                        auto_repairable=True,
                    )
                )
        return issues

    def _check_image_rules(
        self, plan: LayoutPlan, *, drawing_hero: bool
    ) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        for element in plan.elements:
            if element.content_type not in {
                LayoutContentType.IMAGE,
                LayoutContentType.DRAWING,
            }:
                continue
            if element.fit_mode == ImageFit.FILL:
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_IMAGE_DISTORTION,
                        severity=LayoutIssueSeverity.ERROR,
                        element_ids=[element.id],
                        message=f"Element {element.id} uses distorting fill fit.",
                        suggestion="Use contain or cover instead of fill.",
                        auto_repairable=True,
                    )
                )
            is_drawing = element.content_type == LayoutContentType.DRAWING or (
                drawing_hero and element.role == LayoutElementRole.HERO_VISUAL
            )
            if is_drawing and element.crop_policy not in {
                None,
                CropPolicy.NONE,
                CropPolicy.SAFE_TRIM,
                CropPolicy.FORBIDDEN,
            }:
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_DRAWING_CROPPED,
                        severity=LayoutIssueSeverity.CRITICAL,
                        element_ids=[element.id],
                        message=f"Technical drawing {element.id} must not use cover crop.",
                        suggestion="Use contain fit with forbidden/safe crop policy.",
                        auto_repairable=True,
                    )
                )
            if is_drawing and element.fit_mode not in {None, ImageFit.CONTAIN, ImageFit.NONE}:
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_DRAWING_CROPPED,
                        severity=LayoutIssueSeverity.ERROR,
                        element_ids=[element.id],
                        message=f"Technical drawing {element.id} must use contain fit.",
                        suggestion="Set fit_mode to contain.",
                        auto_repairable=True,
                    )
                )
        return issues

    def _check_hero_dominance(
        self, plan: LayoutPlan, safe: Rect, min_ratio: float
    ) -> list[LayoutValidationIssue]:
        if plan.hero_element_id is None:
            return []
        hero = plan.element_by_id(plan.hero_element_id)
        if hero is None:
            return []
        # Only enforce for drawing/hero families where hero is expected to dominate.
        if plan.layout_family.value not in {"drawing_focus", "hero"}:
            return []
        ratio = hero.area / max(safe.area, 1e-6)
        if ratio + 1e-6 < min_ratio:
            return [
                LayoutValidationIssue(
                    rule_code=LAYOUT_HERO_NOT_DOMINANT,
                    severity=LayoutIssueSeverity.WARNING,
                    element_ids=[hero.id],
                    message=(
                        f"Hero area ratio {ratio:.2f} is below minimum {min_ratio:.2f}."
                    ),
                    suggestion="Enlarge the hero visual.",
                    auto_repairable=True,
                )
            ]
        return []

    def _check_whitespace(
        self, plan: LayoutPlan, min_ratio: float, max_ratio: float
    ) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        if plan.whitespace_ratio + 1e-6 < min_ratio:
            issues.append(
                LayoutValidationIssue(
                    rule_code=LAYOUT_INSUFFICIENT_WHITESPACE,
                    severity=LayoutIssueSeverity.WARNING,
                    element_ids=[],
                    message=f"Whitespace ratio {plan.whitespace_ratio:.2f} is too low.",
                    suggestion="Reduce content density or enlarge page margins.",
                    auto_repairable=False,
                )
            )
        if plan.whitespace_ratio - 1e-6 > max_ratio:
            issues.append(
                LayoutValidationIssue(
                    rule_code=LAYOUT_EXCESSIVE_DENSITY,
                    severity=LayoutIssueSeverity.INFO,
                    element_ids=[],
                    message=(
                        f"Whitespace ratio {plan.whitespace_ratio:.2f} exceeds "
                        f"comfortable maximum {max_ratio:.2f}."
                    ),
                    suggestion="Add supporting content or tighten spacing.",
                    auto_repairable=False,
                )
            )
        # Misnamed historically in checklist: excessive density when whitespace too low.
        occupied_ratio = 1.0 - plan.whitespace_ratio
        if occupied_ratio > 0.92:
            issues.append(
                LayoutValidationIssue(
                    rule_code=LAYOUT_EXCESSIVE_DENSITY,
                    severity=LayoutIssueSeverity.WARNING,
                    element_ids=[],
                    message="Page content density is excessive.",
                    suggestion="Remove secondary content or split the slide.",
                    auto_repairable=False,
                )
            )
        return issues

    def _check_alignment(self, plan: LayoutPlan) -> list[LayoutValidationIssue]:
        issues: list[LayoutValidationIssue] = []
        by_role: dict[LayoutElementRole, list[LayoutElement]] = {}
        for element in plan.elements:
            by_role.setdefault(element.role, []).append(element)
        for role, group in by_role.items():
            if role not in {
                LayoutElementRole.SUPPORTING_VISUAL,
                LayoutElementRole.METRIC,
                LayoutElementRole.BODY_TEXT,
            }:
                continue
            if len(group) < 2:
                continue
            xs = [el.x for el in group]
            ys = [el.y for el in group]
            widths = [el.width for el in group]
            if (
                max(xs) - min(xs) > 0.05
                and max(ys) - min(ys) > 0.05
                and max(widths) - min(widths) > 0.08
            ):
                issues.append(
                    LayoutValidationIssue(
                        rule_code=LAYOUT_INCONSISTENT_ALIGNMENT,
                        severity=LayoutIssueSeverity.WARNING,
                        element_ids=[el.id for el in group],
                        message=f"Elements with role {role.value} are inconsistently aligned.",
                        suggestion="Align shared edges or equalize widths.",
                        auto_repairable=True,
                    )
                )
        return issues

    def _score(
        self, plan: LayoutPlan, issues: list[LayoutValidationIssue]
    ) -> LayoutScore:
        """Compute Layout Quality Score from geometric / rule findings only.

        Explicitly excludes semantic visual judgment (image–message fit, color
        harmony, multi-page rhythm, etc.) — that belongs to a future Visual Critic.
        """
        critical = sum(1 for i in issues if i.severity == LayoutIssueSeverity.CRITICAL)
        errors = sum(1 for i in issues if i.severity == LayoutIssueSeverity.ERROR)
        warnings = sum(1 for i in issues if i.severity == LayoutIssueSeverity.WARNING)

        validity = max(0.0, 1.0 - critical * 0.4 - errors * 0.15)
        readability = max(0.0, 1.0 - sum(
            0.2 for i in issues if i.rule_code in {LAYOUT_TEXT_OVERFLOW, LAYOUT_FONT_TOO_SMALL}
        ))
        hierarchy = 1.0 if plan.hero_element_id or plan.elements_by_role(
            LayoutElementRole.LEAD_STATEMENT
        ) else 0.7
        if any(i.rule_code == LAYOUT_HERO_NOT_DOMINANT for i in issues):
            hierarchy -= 0.25
        alignment = max(
            0.0,
            1.0
            - 0.2
            * sum(1 for i in issues if i.rule_code == LAYOUT_INCONSISTENT_ALIGNMENT),
        )
        whitespace = 1.0
        if any(
            i.rule_code
            in {LAYOUT_INSUFFICIENT_WHITESPACE, LAYOUT_EXCESSIVE_DENSITY}
            for i in issues
        ):
            whitespace = 0.6
        asset_usage = 1.0
        asset_codes = {
            LAYOUT_IMAGE_DISTORTION,
            LAYOUT_DRAWING_CROPPED,
            LAYOUT_MISSING_ASSET_REFERENCE,
            LAYOUT_UNRESOLVED_ASSET_PATH,
            LAYOUT_HERO_ASSET_MISSING,
        }
        if any(i.rule_code in asset_codes for i in issues):
            asset_usage = 0.4
            if any(i.rule_code == LAYOUT_HERO_ASSET_MISSING for i in issues):
                asset_usage = 0.15
        consistency = max(0.0, 1.0 - warnings * 0.05)
        total = (
            validity * 0.3
            + readability * 0.15
            + hierarchy * 0.15
            + alignment * 0.1
            + whitespace * 0.1
            + asset_usage * 0.1
            + consistency * 0.1
        )
        return LayoutScore(
            validity_score=round(validity, 3),
            readability_score=round(readability, 3),
            hierarchy_score=round(max(0.0, hierarchy), 3),
            alignment_score=round(alignment, 3),
            whitespace_score=round(whitespace, 3),
            asset_usage_score=round(asset_usage, 3),
            consistency_score=round(consistency, 3),
            total_score=round(max(0.0, min(1.0, total)), 3),
        )
