"""Product-facing QA buckets — actionable issue groups, not a mixed quality score.

Architects should see three queues:

* **事实 QA** — numbers, citations, evidence, units, page↔source consistency
* **表达 QA** — density, hierarchy, narrative jumps, image–text, missing legends
* **渲染 QA** — overflow, font swap, missing images, occlusion, PPTX↔preview, editability
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class ProductQaBucket(StrEnum):
    FACT = "fact"
    EXPRESSION = "expression"
    RENDER = "render"


PRODUCT_QA_BUCKET_LABELS_ZH: dict[ProductQaBucket, str] = {
    ProductQaBucket.FACT: "事实 QA",
    ProductQaBucket.EXPRESSION: "表达 QA",
    ProductQaBucket.RENDER: "渲染 QA",
}

PRODUCT_QA_BUCKET_CAPTIONS_ZH: dict[ProductQaBucket, str] = {
    ProductQaBucket.FACT: "数字冲突、引用缺失、结论无证据、单位错误、页面与资料不一致",
    ProductQaBucket.EXPRESSION: "文字过多、主次不清、叙事跳跃、图文关系、图例缺失",
    ProductQaBucket.RENDER: "溢出、字体替换、图像缺失、对象遮挡、PPTX 与截图不一致、不可编辑对象过多",
}

# Exact codes first (longest / most specific), then prefixes — first match wins.
_EXACT_BUCKETS: dict[str, ProductQaBucket] = {
    # Fact
    "CONTENT.CONCLUSION_WITHOUT_EVIDENCE": ProductQaBucket.FACT,
    "CONTENT.SPECULATION_AS_FACT": ProductQaBucket.FACT,
    "CONTENT.METRIC_MISSING_UNIT": ProductQaBucket.FACT,
    "CONTENT.EXTERNAL_FACT_NO_CITATION": ProductQaBucket.FACT,
    "ARCH.INCONSISTENT_AREA_UNITS": ProductQaBucket.FACT,
    "ARCH.PROBLEM_WITHOUT_EVIDENCE": ProductQaBucket.FACT,
    "ARCH.REFERENCE_AS_PROJECT": ProductQaBucket.FACT,
    "ARCH.AI_AS_SITE_PHOTO": ProductQaBucket.FACT,
    "ARCH.IMAGE_IDENTITY_UNCLEAR": ProductQaBucket.FACT,
    "SEMANTIC.METRIC_WITHOUT_UNIT": ProductQaBucket.FACT,
    "SEMANTIC.EXTERNAL_FACT_WITHOUT_CITATION": ProductQaBucket.FACT,
    "SEMANTIC.AI_IMAGE_PRESENTED_AS_REAL_PROJECT": ProductQaBucket.FACT,
    "SEMANTIC.STOCK_IMAGE_PRESENTED_AS_PROJECT": ProductQaBucket.FACT,
    "SEMANTIC.REFERENCE_ASSET_USED_AS_PROJECT_ASSET": ProductQaBucket.FACT,
    "SEMANTIC.PROJECT_ASSET_WITHOUT_SOURCE": ProductQaBucket.FACT,
    "SEMANTIC.ISSUE_WITHOUT_EVIDENCE": ProductQaBucket.FACT,
    "DECK.WEAK_SECTION_EVIDENCE": ProductQaBucket.FACT,
    "DECK.RESOLUTION_UNSUPPORTED": ProductQaBucket.FACT,
    "GRAMMAR.MISSING_EVIDENCE_SLOT": ProductQaBucket.FACT,
    # Expression
    "CONTENT.NO_CLEAR_CONCLUSION": ProductQaBucket.EXPRESSION,
    "CONTENT.TITLE_NOT_CONCLUSION": ProductQaBucket.EXPRESSION,
    "CONTENT.TEXT_PURPOSE_MISMATCH": ProductQaBucket.EXPRESSION,
    "CONTENT.REPETITIVE": ProductQaBucket.EXPRESSION,
    "CONTENT.TOO_VAGUE": ProductQaBucket.EXPRESSION,
    "CONTENT.IMPORTANT_MISSING": ProductQaBucket.EXPRESSION,
    "LAYOUT.HIGH_TEXT_DENSITY": ProductQaBucket.EXPRESSION,
    "LAYOUT.BULLET_TOO_LONG": ProductQaBucket.EXPRESSION,
    "LAYOUT.TOO_MANY_BULLETS": ProductQaBucket.EXPRESSION,
    "LAYOUT.MESSAGE_TOO_LONG": ProductQaBucket.EXPRESSION,
    "LAYOUT.TITLE_HIERARCHY_WEAK": ProductQaBucket.EXPRESSION,
    "LAYOUT.NO_VISUAL_FOCUS": ProductQaBucket.EXPRESSION,
    "LAYOUT.WHITESPACE_IMBALANCE": ProductQaBucket.EXPRESSION,
    "LAYOUT.TOO_DENSE": ProductQaBucket.EXPRESSION,
    "LAYOUT.TOO_EMPTY": ProductQaBucket.EXPRESSION,
    "LAYOUT.WEAK_CONTRAST": ProductQaBucket.EXPRESSION,
    "LAYOUT.DECK_RHYTHM_REPEAT": ProductQaBucket.EXPRESSION,
    "ARCH.FLOW_DIAGRAM_MISSING_LEGEND": ProductQaBucket.EXPRESSION,
    "ARCH.STRATEGY_DETACHED": ProductQaBucket.EXPRESSION,
    "ARCH.BEFORE_AFTER_MISMATCH": ProductQaBucket.EXPRESSION,
    "ARCH.DRAWING_TOO_SMALL": ProductQaBucket.EXPRESSION,
    "ARCH.ANNOTATIONS_UNREADABLE": ProductQaBucket.EXPRESSION,
    "ARCH.SITE_PLAN_NO_ORIENTATION": ProductQaBucket.EXPRESSION,
    "VISUAL.HIGH_TEXT_DENSITY": ProductQaBucket.EXPRESSION,
    "VISUAL.MISSING_LEGEND": ProductQaBucket.EXPRESSION,
    "VISUAL.MISSING_NORTH_ARROW": ProductQaBucket.EXPRESSION,
    "SEMANTIC.TEXT_NOT_EXPLAINING_VISUAL": ProductQaBucket.EXPRESSION,
    "SEMANTIC.VISUAL_WITHOUT_CAPTION": ProductQaBucket.EXPRESSION,
    "SEMANTIC.TOO_MANY_EQUAL_WEIGHT_IMAGES": ProductQaBucket.EXPRESSION,
    "SEMANTIC.BEFORE_AFTER_MISMATCH": ProductQaBucket.EXPRESSION,
    "SEMANTIC.STRATEGY_WITHOUT_TARGET": ProductQaBucket.EXPRESSION,
    "SEMANTIC.CAPTION_MISSING": ProductQaBucket.EXPRESSION,
    "SEMANTIC.DRAWING_TOO_SMALL": ProductQaBucket.EXPRESSION,
    "GRAMMAR.STRATEGY_WITHOUT_PROBLEM_REF": ProductQaBucket.EXPRESSION,
    # Render
    "LAYOUT.OVERLAP": ProductQaBucket.RENDER,
    "LAYOUT.ELEMENT_OVERLAP": ProductQaBucket.RENDER,
    "LAYOUT.OUT_OF_BOUNDS": ProductQaBucket.RENDER,
    "LAYOUT.TEXT_OVERFLOW": ProductQaBucket.RENDER,
    "LAYOUT.FONT_TOO_SMALL": ProductQaBucket.RENDER,
    "LAYOUT.FONT_SUBSTITUTION": ProductQaBucket.RENDER,
    "LAYOUT.IMAGE_DISTORTED": ProductQaBucket.RENDER,
    "LAYOUT.BLANK_PAGE": ProductQaBucket.RENDER,
    "LAYOUT.MISSING_ASSET": ProductQaBucket.RENDER,
    "LAYOUT.LOW_RESOLUTION_ASSET": ProductQaBucket.RENDER,
    "LAYOUT.EXTREME_ASPECT_RATIO": ProductQaBucket.RENDER,
    "SEMANTIC.IMAGE_NOT_RENDERED": ProductQaBucket.RENDER,
    "SEMANTIC.TEXT_OVERFLOW": ProductQaBucket.RENDER,
    "SEMANTIC.FONT_TOO_SMALL": ProductQaBucket.RENDER,
    "SEMANTIC.SCENE_PPTX_NODE_MISMATCH": ProductQaBucket.RENDER,
    "SEMANTIC.FONT_FALLBACK_CHANGED_LAYOUT": ProductQaBucket.RENDER,
    "SEMANTIC.DRAWING_COVER_MODE_FORBIDDEN": ProductQaBucket.RENDER,
    "SEMANTIC.DRAWING_CROP_RISK": ProductQaBucket.RENDER,
    "ARCH.DRAWING_DISTORTED": ProductQaBucket.RENDER,
    "ARCH.DRAWING_CRITICAL_CROP": ProductQaBucket.RENDER,
    "VISUAL.CONTENT_CLIPPED": ProductQaBucket.RENDER,
    "VISUAL.ASSET_UNREADABLE": ProductQaBucket.RENDER,
    "VISUAL.ASSET_FILE_NOT_FOUND": ProductQaBucket.RENDER,
    "VISUAL.ASSET_FORMAT_UNSUPPORTED": ProductQaBucket.RENDER,
    "VISUAL.ASSET_DECODE_FAILED": ProductQaBucket.RENDER,
    "VISUAL.ASSET_PERMISSION_DENIED": ProductQaBucket.RENDER,
    "VISUAL.ASSET_RECORD_MISSING": ProductQaBucket.RENDER,
    "VISUAL.DIMENSIONS_TOO_SMALL": ProductQaBucket.RENDER,
}

_PREFIX_BUCKETS: tuple[tuple[str, ProductQaBucket], ...] = (
    ("EVIDENCE.", ProductQaBucket.FACT),
    ("PROVENANCE.", ProductQaBucket.FACT),
    ("CONTENT.", ProductQaBucket.FACT),
    ("IMAGE_TEXT.", ProductQaBucket.EXPRESSION),
    ("CRITIC.", ProductQaBucket.EXPRESSION),
    ("DECK.", ProductQaBucket.EXPRESSION),
    ("RHYTHM.", ProductQaBucket.EXPRESSION),
    ("POST_RENDER.", ProductQaBucket.RENDER),
    ("RENDER.", ProductQaBucket.RENDER),
    ("EDIT.", ProductQaBucket.RENDER),
    ("ASSET.", ProductQaBucket.RENDER),
    ("VISUAL.ASSET_", ProductQaBucket.RENDER),
    ("VISUAL.", ProductQaBucket.EXPRESSION),
    ("LAYOUT.", ProductQaBucket.EXPRESSION),
    ("ARCH.", ProductQaBucket.EXPRESSION),
    ("SEMANTIC.", ProductQaBucket.EXPRESSION),
    ("GRAMMAR.", ProductQaBucket.EXPRESSION),
)


class ProductQaFinding(DomainModel):
    """One partner-facing finding tagged with a product QA bucket."""

    bucket: ProductQaBucket
    rule_code: str = ""
    title: str = ""
    detail: str = ""
    severity: str = ""
    source: str = ""


class ProductQaBucketSummary(DomainModel):
    bucket: ProductQaBucket
    label: str
    caption: str
    count: int = 0
    findings: list[ProductQaFinding] = Field(default_factory=list)


def product_qa_bucket_for_code(rule_code: str) -> ProductQaBucket:
    """Map a machine rule/check code to the product QA bucket."""
    normalized = (rule_code or "").strip()
    if not normalized:
        return ProductQaBucket.EXPRESSION
    exact = _EXACT_BUCKETS.get(normalized)
    if exact is not None:
        return exact
    upper = normalized.upper()
    exact = _EXACT_BUCKETS.get(upper)
    if exact is not None:
        return exact
    for prefix, bucket in _PREFIX_BUCKETS:
        if normalized.startswith(prefix) or upper.startswith(prefix):
            return bucket
    return ProductQaBucket.EXPRESSION


def make_product_qa_finding(
    *,
    rule_code: str = "",
    title: str = "",
    detail: str = "",
    severity: str = "",
    source: str = "",
    bucket: ProductQaBucket | None = None,
) -> ProductQaFinding:
    resolved = bucket or product_qa_bucket_for_code(rule_code)
    return ProductQaFinding(
        bucket=resolved,
        rule_code=(rule_code or "").strip(),
        title=(title or "").strip() or (rule_code or "问题"),
        detail=(detail or "").strip(),
        severity=(severity or "").strip(),
        source=(source or "").strip(),
    )


def group_product_qa_findings(
    findings: list[ProductQaFinding],
    *,
    limit_per_bucket: int = 8,
) -> list[ProductQaBucketSummary]:
    """Return summaries in fact → expression → render order.

    Per-slide critic/deck findings often repeat the same rule across a long
    deck. Collapse by ``rule_code`` so partners see actionable *types* (with
    occurrence counts) instead of an inflated raw page×finding total.
    """
    buckets = (
        ProductQaBucket.FACT,
        ProductQaBucket.EXPRESSION,
        ProductQaBucket.RENDER,
    )
    grouped: dict[ProductQaBucket, list[ProductQaFinding]] = {b: [] for b in buckets}
    for item in findings:
        grouped[item.bucket].append(item)
    summaries: list[ProductQaBucketSummary] = []
    for bucket in buckets:
        collapsed = _collapse_findings_by_rule(grouped[bucket])
        summaries.append(
            ProductQaBucketSummary(
                bucket=bucket,
                label=PRODUCT_QA_BUCKET_LABELS_ZH[bucket],
                caption=PRODUCT_QA_BUCKET_CAPTIONS_ZH[bucket],
                count=len(collapsed),
                findings=collapsed[:limit_per_bucket],
            )
        )
    return summaries


def _collapse_findings_by_rule(
    findings: list[ProductQaFinding],
) -> list[ProductQaFinding]:
    """One row per rule_code (or title), highest severity first, with 处 counts."""
    if not findings:
        return []
    by_key: dict[str, list[ProductQaFinding]] = {}
    for item in findings:
        key = (item.rule_code or "").strip() or item.title or "问题"
        by_key.setdefault(key, []).append(item)

    severity_rank = {"error": 0, "warning": 1, "info": 2, "": 3}
    collapsed: list[tuple[int, ProductQaFinding]] = []
    for key, group in by_key.items():
        group_sorted = sorted(
            group,
            key=lambda f: severity_rank.get((f.severity or "").lower(), 3),
        )
        base = group_sorted[0]
        n = len(group)
        title = base.title if n == 1 else f"{base.title}（{n} 处）"
        collapsed.append(
            (
                n,
                ProductQaFinding(
                    bucket=base.bucket,
                    rule_code=base.rule_code or key,
                    title=title,
                    detail=base.detail,
                    severity=base.severity,
                    source=base.source,
                ),
            )
        )
    collapsed.sort(
        key=lambda pair: (
            severity_rank.get((pair[1].severity or "").lower(), 3),
            -pair[0],
            pair[1].rule_code,
        )
    )
    return [item for _, item in collapsed]


def collect_product_qa_from_sources(
    *,
    review_issues: list[dict] | None = None,
    deck_qa_report: dict | None = None,
    critic_report: dict | None = None,
    quality_issues: list[dict] | None = None,
) -> list[ProductQaFinding]:
    """Normalize heterogeneous QA payloads into product findings."""
    out: list[ProductQaFinding] = []
    for raw in review_issues or []:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("rule_code") or "")
        out.append(
            make_product_qa_finding(
                rule_code=code,
                title=str(raw.get("title") or code),
                detail=str(raw.get("description") or raw.get("suggestion") or ""),
                severity=str(raw.get("severity") or ""),
                source="review",
            )
        )
    if isinstance(deck_qa_report, dict):
        for raw in deck_qa_report.get("findings") or []:
            if not isinstance(raw, dict):
                continue
            code = str(raw.get("rule_code") or "")
            out.append(
                make_product_qa_finding(
                    rule_code=code,
                    title=str(raw.get("message") or code),
                    detail=str(raw.get("suggestion") or ""),
                    severity=str(raw.get("severity") or ""),
                    source="deck_qa",
                )
            )
    if isinstance(critic_report, dict):
        for raw in critic_report.get("findings") or []:
            if not isinstance(raw, dict):
                continue
            code = str(raw.get("rule_code") or "")
            out.append(
                make_product_qa_finding(
                    rule_code=code,
                    title=str(raw.get("message") or code),
                    detail=str(raw.get("suggestion") or ""),
                    severity=str(raw.get("severity") or ""),
                    source="critic",
                )
            )
    for raw in quality_issues or []:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or raw.get("rule_code") or "")
        out.append(
            make_product_qa_finding(
                rule_code=code,
                title=str(raw.get("message") or code),
                detail=str(raw.get("suggested_fix") or raw.get("evidence") or ""),
                severity=str(raw.get("severity") or ""),
                source="quality",
            )
        )
    return out
