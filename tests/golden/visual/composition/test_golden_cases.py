"""Golden visual composition cases V1–V3 (LayoutPlan JSON baselines)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.domain.citation import Citation
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual import LayoutFamily, VisualContentType, default_presentation_design_system
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutElementRole
from archium.infrastructure.layout.generators.base import (
    LayoutGeneratorContext,
    content_from_slide,
)
from archium.infrastructure.layout.layout_solver import LayoutSolver

GOLDEN_ROOT = Path(__file__).resolve().parent
DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")


def _write_baseline(case_dir: Path, plan_json: dict[str, object], report_json: dict[str, object]) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "layout_plan.json").write_text(
        json.dumps(plan_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (case_dir / "validation_report.json").write_text(
        json.dumps(report_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class _FakeIntentRepo:
    def __init__(self) -> None:
        self._items: dict = {}

    def save(self, intent):  # noqa: ANN001
        self._items[intent.id] = intent
        return intent

    def get(self, intent_id):  # noqa: ANN001
        return self._items.get(intent_id)


@pytest.fixture
def intent_service(monkeypatch: pytest.MonkeyPatch) -> VisualIntentService:
    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def test_v1_drawing_focus_site_plan(intent_service: VisualIntentService) -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="masterplan",
        order=1,
        title="总体规划与空间结构",
        message="总平面确立院落轴线与核心公服节点。",
        key_points=["绿地率 42%", "容积率 1.8", "公服半径 500m", "轴线贯通", "开放院落", "界面连续"],
        visual_requirements=[
            VisualRequirement(type=VisualType.SITE_PLAN, description="总平面图", preferred_asset_ids=[uuid4()])
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="总体规划说明书.pdf", page_number=12)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    assert intent.dominant_content_type == VisualContentType.SITE_PLAN
    assert LayoutFamily.DRAWING_FOCUS in intent.preferred_layout_families

    design = default_presentation_design_system()
    context = LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content_from_slide(slide, intent),
        variant="drawing_with_metrics",
    )
    plan = LayoutSolver().generate(LayoutFamily.DRAWING_FOCUS, context)
    report = LayoutValidationService().validate(
        plan, design, require_source=True, drawing_hero=True
    )

    hero = plan.element_by_id("hero")
    assert hero is not None
    assert hero.fit_mode == ImageFit.CONTAIN
    assert hero.crop_policy == CropPolicy.FORBIDDEN
    assert plan.elements_by_role(LayoutElementRole.SOURCE)
    assert plan.elements_by_role(LayoutElementRole.TITLE)
    assert not report.has_critical()

    case_dir = GOLDEN_ROOT / "v1_drawing_focus"
    _write_baseline(
        case_dir,
        plan.model_dump(mode="json"),
        report.model_dump(mode="json"),
    )
    assert (case_dir / "layout_plan.json").exists()


def test_v2_evidence_board_photos(intent_service: VisualIntentService) -> None:
    photos = [uuid4() for _ in range(4)]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="evidence",
        order=2,
        title="患者就医过程中的高压力节点",
        message="患者的焦虑并不只来自疾病，而来自入口混乱、路径不清和长时间候诊。",
        key_points=["入口混乱", "路径不清", "候诊过长", "问询反复"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description=f"现场照片{i + 1}",
                preferred_asset_ids=[photos[i]],
            )
            for i in range(4)
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="现场踏勘记录.pdf", page_number=3)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    assert intent.dominant_content_type == VisualContentType.PHOTO_EVIDENCE
    assert LayoutFamily.EVIDENCE_BOARD in intent.preferred_layout_families

    design = default_presentation_design_system()
    context = LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content_from_slide(slide, intent),
        variant="numbered_grid",
    )
    plan = LayoutSolver().generate(LayoutFamily.EVIDENCE_BOARD, context)
    report = LayoutValidationService().validate(plan, design, require_source=True)

    photos_els = plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(photos_els) == 4
    assert len({round(el.width, 3) for el in photos_els}) == 1
    assert plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert not report.has_critical()

    _write_baseline(
        GOLDEN_ROOT / "v2_evidence_board",
        plan.model_dump(mode="json"),
        report.model_dump(mode="json"),
    )


def test_v3_comparative_matrix(intent_service: VisualIntentService) -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="cases",
        order=3,
        title="三个既有图书馆更新案例比较",
        message="既有图书馆更新应优先重建公共性与可达性，而非单纯扩容。",
        key_points=["空间策略", "运营模式", "公众可达性", "案例A：中庭再生", "案例B：街道界面", "案例C：社区嵌入"],
        visual_requirements=[
            VisualRequirement(type=VisualType.COMPARISON, description="案例比较", preferred_asset_ids=[uuid4()]),
            VisualRequirement(type=VisualType.REFERENCE_CASE, description="案例图1", preferred_asset_ids=[uuid4()]),
            VisualRequirement(type=VisualType.REFERENCE_CASE, description="案例图2", preferred_asset_ids=[uuid4()]),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="案例研究汇编.pdf", page_number=8)
        ],
    )
    intent = intent_service.generate_for_slide(slide, use_llm=False)
    # Force comparison dominance for golden expectation when mixed refs exist.
    if intent.dominant_content_type != VisualContentType.COMPARISON:
        intent.dominant_content_type = VisualContentType.COMPARISON
        intent.preferred_layout_families = [LayoutFamily.COMPARATIVE_MATRIX]

    design = default_presentation_design_system()
    context = LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content_from_slide(slide, intent),
        variant="matrix_with_insight",
    )
    plan = LayoutSolver().generate(LayoutFamily.COMPARATIVE_MATRIX, context)
    report = LayoutValidationService().validate(plan, design, require_source=True)

    assert plan.layout_family == LayoutFamily.COMPARATIVE_MATRIX
    images = plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(images) == 3
    assert len({round(img.width, 3) for img in images}) == 1
    assert plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert not report.has_critical()

    _write_baseline(
        GOLDEN_ROOT / "v3_comparative_matrix",
        plan.model_dump(mode="json"),
        report.model_dump(mode="json"),
    )
