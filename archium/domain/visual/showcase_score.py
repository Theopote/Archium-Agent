"""Showcase investor scorecard (Presentation Engine v0.3 Phase 4).

Separate from ``HumanVisualReview`` (1–5 experimental / formal issue gates).
Investor demos use five dimensions × /10 = /50 with an explicit stage gate.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from archium.domain._base import DomainModel

SHOWCASE_SCORE_SCHEMA = "showcase_investor_score_v1"
SHOWCASE_TOTAL_MAX = 50
SHOWCASE_GATE_TOTAL_MIN = 35
SHOWCASE_GATE_AESTHETIC_MIN = 7
SHOWCASE_GATE_PROFESSIONALISM_MIN = 7

SHOWCASE_DIMENSION_KEYS: tuple[str, ...] = (
    "information_logic",
    "architectural_expression",
    "aesthetic",
    "professionalism",
    "editability_studio",
)

SHOWCASE_DIMENSION_LABELS_ZH: dict[str, str] = {
    "information_logic": "信息逻辑",
    "architectural_expression": "建筑表达",
    "aesthetic": "美观",
    "professionalism": "专业度",
    "editability_studio": "可修改性（Studio）",
}


class ShowcaseInvestorDimensions(DomainModel):
    """Five investor-facing scores, each 0–10 (None = not yet scored)."""

    information_logic: int | None = Field(default=None, ge=0, le=10)
    architectural_expression: int | None = Field(default=None, ge=0, le=10)
    aesthetic: int | None = Field(default=None, ge=0, le=10)
    professionalism: int | None = Field(default=None, ge=0, le=10)
    editability_studio: int | None = Field(default=None, ge=0, le=10)


class ShowcaseGateResult(DomainModel):
    """Stage-gate evaluation for Showcase Case packs."""

    complete: bool
    total: int | None = None
    total_max: int = SHOWCASE_TOTAL_MAX
    total_min: int = SHOWCASE_GATE_TOTAL_MIN
    aesthetic_min: int = SHOWCASE_GATE_AESTHETIC_MIN
    professionalism_min: int = SHOWCASE_GATE_PROFESSIONALISM_MIN
    passed: bool = False
    failures: list[str] = Field(default_factory=list)


class ShowcaseInvestorScore(DomainModel):
    """Human scorecard artifact for a Showcase case (not auto-filled by Critic)."""

    case_id: str = Field(min_length=1)
    schema_version: str = SHOWCASE_SCORE_SCHEMA
    style_preset_id: str | None = None
    dimensions: ShowcaseInvestorDimensions = Field(
        default_factory=ShowcaseInvestorDimensions
    )
    notes: str = ""
    reviewer: str | None = None
    demo_tour_ok: bool | None = Field(
        default=None,
        description="Cover → site → strategy → atmosphere pages openable.",
    )

    @field_validator("schema_version")
    @classmethod
    def _schema_must_match(cls, value: str) -> str:
        if value != SHOWCASE_SCORE_SCHEMA:
            raise ValueError(
                f"Unsupported showcase score schema: {value!r} "
                f"(expected {SHOWCASE_SCORE_SCHEMA!r})"
            )
        return value

    @property
    def total(self) -> int | None:
        values = [
            self.dimensions.information_logic,
            self.dimensions.architectural_expression,
            self.dimensions.aesthetic,
            self.dimensions.professionalism,
            self.dimensions.editability_studio,
        ]
        if any(value is None for value in values):
            return None
        return int(sum(values))  # type: ignore[arg-type]

    @property
    def is_complete(self) -> bool:
        return self.total is not None

    def evaluate_gate(
        self,
        *,
        total_min: int = SHOWCASE_GATE_TOTAL_MIN,
        aesthetic_min: int = SHOWCASE_GATE_AESTHETIC_MIN,
        professionalism_min: int = SHOWCASE_GATE_PROFESSIONALISM_MIN,
    ) -> ShowcaseGateResult:
        failures: list[str] = []
        dims = self.dimensions
        if not self.is_complete:
            missing = [
                key
                for key in SHOWCASE_DIMENSION_KEYS
                if getattr(dims, key) is None
            ]
            return ShowcaseGateResult(
                complete=False,
                total=None,
                total_min=total_min,
                aesthetic_min=aesthetic_min,
                professionalism_min=professionalism_min,
                passed=False,
                failures=[f"incomplete_scores:{','.join(missing)}"],
            )

        total = self.total
        assert total is not None
        assert dims.aesthetic is not None
        assert dims.professionalism is not None

        if total < total_min:
            failures.append(f"total<{total_min} (got {total})")
        if dims.aesthetic < aesthetic_min:
            failures.append(f"aesthetic<{aesthetic_min} (got {dims.aesthetic})")
        if dims.professionalism < professionalism_min:
            failures.append(
                f"professionalism<{professionalism_min} (got {dims.professionalism})"
            )

        return ShowcaseGateResult(
            complete=True,
            total=total,
            total_min=total_min,
            aesthetic_min=aesthetic_min,
            professionalism_min=professionalism_min,
            passed=not failures,
            failures=failures,
        )


def empty_showcase_score(
    case_id: str,
    *,
    style_preset_id: str | None = "architecture_technical",
) -> ShowcaseInvestorScore:
    """Blank scorecard template for human fill-in."""
    return ShowcaseInvestorScore(
        case_id=case_id,
        style_preset_id=style_preset_id,
        dimensions=ShowcaseInvestorDimensions(),
    )


def showcase_score_from_dict(payload: dict) -> ShowcaseInvestorScore:
    """Parse a scorecard JSON object (template or filled)."""
    return ShowcaseInvestorScore.model_validate(payload)
