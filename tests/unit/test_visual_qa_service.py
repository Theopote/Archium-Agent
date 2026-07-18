"""Unit tests for explainable visual QA."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.automated_review_service import AutomatedReviewService, critical_export_block_messages
from archium.application.visual_qa_service import VisualQAService
from archium.config.settings import Settings
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, ProjectType, ReviewSeverity, VisualType
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import (
    AssetRepository,
    PresentationRepository,
    ProjectRepository,
)
from archium.infrastructure.vision.analyzer import analyze_image
from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

pytest.importorskip("PIL")


def _draw_north_arrow(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    corner = width - 80
    draw.polygon([(corner + 40, 10), (corner + 10, 85), (corner + 70, 85)], fill=(10, 10, 10))
    draw.text((corner + 32, 86), "N", fill=(10, 10, 10))


def _draw_legend_strip(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    base_y = height - 70
    colors = [(220, 30, 30), (30, 120, 220), (40, 180, 80)]
    for index, color in enumerate(colors):
        x = 40 + index * 90
        draw.rectangle((x, base_y, x + 50, base_y + 20), fill=color)
        draw.text((x, base_y + 24), f"L{index + 1}", fill=(0, 0, 0))


def create_site_plan_image(path: Path, *, with_north: bool = True, with_legend: bool = True) -> Path:
    image = Image.new("RGB", (1200, 900), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 120, 1080, 780), outline=(30, 30, 30), width=3)
    draw.line((120, 450, 1080, 450), fill=(80, 80, 80), width=2)
    draw.line((600, 120, 600, 780), fill=(80, 80, 80), width=2)
    if with_north:
        _draw_north_arrow(image)
    if with_legend:
        _draw_legend_strip(image)
    image.save(path, format="PNG")
    return path


@pytest.fixture
def project_and_asset(db_session: Session, tmp_path: Path) -> tuple[object, Asset]:
    project = ProjectRepository(db_session).create(
        Project(name="Visual QA Project", project_type=ProjectType.HEALTHCARE)
    )
    image_path = create_site_plan_image(tmp_path / "site_plan.png")
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            filename="site_plan.png",
            path=str(image_path),
            asset_type=AssetType.DRAWING,
            width=1200,
            height=900,
            description="总平面图",
            tags=["site_plan"],
        )
    )
    return project.id, asset


class TestVisualAnalyzer:
    def test_analyze_image_detects_north_arrow_and_legend(self, tmp_path: Path) -> None:
        image_path = create_site_plan_image(tmp_path / "plan.png")
        image = Image.open(image_path)
        report = analyze_image(uuid4(), str(image_path), image)

        assert report.check("north_arrow") is not None
        assert report.check("north_arrow").passed
        assert report.check("legend_region") is not None
        assert report.check("legend_region").passed
        assert report.drawing_type is not None
        assert report.check("drawing_classifier") is not None

    def test_analyze_image_flags_missing_north_arrow(self, tmp_path: Path) -> None:
        image_path = create_site_plan_image(tmp_path / "plan_no_north.png", with_north=False)
        image = Image.open(image_path)
        report = analyze_image(uuid4(), str(image_path), image)

        assert report.check("north_arrow") is not None
        assert not report.check("north_arrow").passed

    def test_analyze_image_flags_small_dimensions(self, tmp_path: Path) -> None:
        image = Image.new("RGB", (640, 480), color=(240, 240, 240))
        report = analyze_image(uuid4(), "small.png", image)

        assert report.check("image_dimensions") is not None
        assert not report.check("image_dimensions").passed


class TestVisualQAService:
    def test_review_slides_suppresses_low_confidence_north_arrow(
        self,
        db_session: Session,
        project_and_asset: tuple[object, Asset],
        tmp_path: Path,
    ) -> None:
        project_id, asset = project_and_asset
        image_path = create_site_plan_image(tmp_path / "no_north.png", with_north=False)
        asset.path = str(image_path)
        presentation = PresentationRepository(db_session).create_presentation(
            Presentation(project_id=project_id, title="Visual QA")  # type: ignore[arg-type]
        )
        slide = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="总平面",
            message="院区总平面布局。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    preferred_asset_ids=[asset.id],
                )
            ],
        )

        issues = VisualQAService(db_session).review_slides(
            presentation.id,
            [slide],
            {asset.id: asset},
        )

        assert not any(issue.rule_code == ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW for issue in issues)

    def test_review_slides_flags_small_dimensions_as_formal_issue(
        self,
        db_session: Session,
        project_and_asset: tuple[object, Asset],
        tmp_path: Path,
    ) -> None:
        project_id, asset = project_and_asset
        small_path = tmp_path / "small_plan.png"
        Image.new("RGB", (640, 480), color=(240, 240, 240)).save(small_path, format="PNG")
        asset.path = str(small_path)
        asset.width = 640
        asset.height = 480
        presentation = PresentationRepository(db_session).create_presentation(
            Presentation(project_id=project_id, title="Small Image QA")  # type: ignore[arg-type]
        )
        slide = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="总平面",
            message="院区总平面布局。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    preferred_asset_ids=[asset.id],
                )
            ],
        )

        issues = VisualQAService(db_session).review_slides(
            presentation.id,
            [slide],
            {asset.id: asset},
        )

        assert any(issue.rule_code == ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL for issue in issues)
        dim_issue = next(
            issue for issue in issues if issue.rule_code == ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL
        )
        assert dim_issue.confidence == 1.0
        assert dim_issue.detection_method == "pillow_heuristic"
        assert not dim_issue.requires_confirmation

    def test_layout_review_runs_visual_qa_when_enabled(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        project = ProjectRepository(db_session).create(
            Project(name="Layout QA Project", project_type=ProjectType.HEALTHCARE)
        )
        small_path = tmp_path / "layout_small.png"
        Image.new("RGB", (640, 480), color=(240, 240, 240)).save(small_path, format="PNG")
        asset = AssetRepository(db_session).create(
            Asset(
                project_id=project.id,
                filename="layout_plan.png",
                path=str(small_path),
                asset_type=AssetType.DRAWING,
                width=640,
                height=480,
                description="总平面图",
                tags=["site_plan"],
            )
        )
        presentation = PresentationRepository(db_session).create_presentation(
            Presentation(project_id=project.id, title="Layout QA")
        )
        slide = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="交通组织",
            message="总平面交通流线需优化。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图交通流线",
                    preferred_asset_ids=[asset.id],
                )
            ],
        )

        issues = AutomatedReviewService(
            db_session,
            settings=Settings(_env_file=None, visual_qa_enabled=True),
        ).run_layout_review(
            presentation.id,
            [slide],
            project_id=project.id,
        )

        assert any(issue.rule_code == ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL for issue in issues)

    def test_layout_review_skips_text_north_hint_when_visual_qa_enabled(
        self,
        db_session: Session,
        project_and_asset: tuple[object, Asset],
    ) -> None:
        project_id, asset = project_and_asset
        presentation = PresentationRepository(db_session).create_presentation(
            Presentation(project_id=project_id, title="Hint Skip")  # type: ignore[arg-type]
        )
        slide = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="总平面",
            message="布局说明。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    preferred_asset_ids=[asset.id],
                )
            ],
        )

        settings = Settings(_env_file=None, visual_qa_enabled=True)
        arch_issues = AutomatedReviewService(db_session, settings=settings).run_architectural_review(
            presentation.id,
            [slide],
        )
        layout_issues = AutomatedReviewService(
            db_session,
            settings=settings,
        ).run_layout_review(
            presentation.id,
            [slide],
            project_id=project_id,  # type: ignore[arg-type]
        )

        assert not any(
            issue.rule_code == ReviewRuleCode.ARCH_PLAN_MISSING_NORTH_ARROW for issue in arch_issues
        )

    def test_review_slides_flags_missing_asset_file_as_high_issue(
        self,
        db_session: Session,
        project_and_asset: tuple[object, Asset],
    ) -> None:
        project_id, asset = project_and_asset
        asset.path = str(Path("/tmp/does-not-exist") / asset.filename)
        presentation = PresentationRepository(db_session).create_presentation(
            Presentation(project_id=project_id, title="Missing Asset")  # type: ignore[arg-type]
        )
        slide = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="总平面",
            message="布局说明。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    preferred_asset_ids=[asset.id],
                    required=True,
                )
            ],
        )

        issues = VisualQAService(db_session).review_slides(
            presentation.id,
            [slide],
            {asset.id: asset},
        )

        assert any(issue.rule_code == ReviewRuleCode.VISUAL_ASSET_FILE_NOT_FOUND for issue in issues)
        load_issue = next(
            issue for issue in issues if issue.rule_code == ReviewRuleCode.VISUAL_ASSET_FILE_NOT_FOUND
        )
        assert load_issue.severity == ReviewSeverity.HIGH
        assert "必需素材" in load_issue.description

    def test_review_slides_analyzes_candidate_assets_and_caches_reports(
        self,
        db_session: Session,
        project_and_asset: tuple[object, Asset],
        tmp_path: Path,
    ) -> None:
        from unittest.mock import patch

        project_id, primary = project_and_asset
        secondary_path = create_site_plan_image(tmp_path / "candidate.png", with_north=True)
        secondary = AssetRepository(db_session).create(
            Asset(
                project_id=project_id,  # type: ignore[arg-type]
                filename="candidate.png",
                path=str(secondary_path),
                asset_type=AssetType.DRAWING,
                width=1200,
                height=900,
            )
        )
        presentation = PresentationRepository(db_session).create_presentation(
            Presentation(project_id=project_id, title="Multi Asset")  # type: ignore[arg-type]
        )
        slide_one = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="对比页",
            message="方案对比。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="方案 A",
                    preferred_asset_ids=[primary.id],
                    candidate_asset_ids=[secondary.id],
                )
            ],
        )
        slide_two = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=1,
            title="复用页",
            message="复用同一素材。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="方案 A 复用",
                    preferred_asset_ids=[primary.id],
                )
            ],
        )

        with patch(
            "archium.application.visual_qa_service.analyze_image",
            wraps=analyze_image,
        ) as analyze_mock:
            issues = VisualQAService(db_session).review_slides(
                presentation.id,
                [slide_one, slide_two],
                {primary.id: primary, secondary.id: secondary},
            )

        assert analyze_mock.call_count == 2
        assert isinstance(issues, list)

    def test_review_slides_reuses_persisted_visual_qa_report(
        self,
        db_session: Session,
        project_and_asset: tuple[object, Asset],
    ) -> None:
        from unittest.mock import patch

        project_id, asset = project_and_asset
        presentation = PresentationRepository(db_session).create_presentation(
            Presentation(project_id=project_id, title="Persisted QA")  # type: ignore[arg-type]
        )
        slide = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="总平面",
            message="布局说明。",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    preferred_asset_ids=[asset.id],
                )
            ],
        )

        with patch(
            "archium.application.visual_qa_service.analyze_image",
            wraps=analyze_image,
        ) as analyze_mock:
            VisualQAService(db_session).review_slides(
                presentation.id,
                [slide],
                {asset.id: asset},
            )
        assert analyze_mock.call_count == 1

        with patch(
            "archium.application.visual_qa_service.analyze_image",
            wraps=analyze_image,
        ) as analyze_mock:
            VisualQAService(db_session).review_slides(
                presentation.id,
                [slide],
                {asset.id: asset},
            )
        assert analyze_mock.call_count == 0


def test_critical_export_block_includes_high_asset_load_issues() -> None:
    from archium.application.automated_review_service import export_blocking_open_issues
    from archium.domain.enums import ReviewCategory, ReviewStatus
    from archium.domain.review import ReviewIssue

    issue = ReviewIssue(
        presentation_id=uuid4(),
        category=ReviewCategory.VISUAL,
        severity=ReviewSeverity.HIGH,
        rule_code=ReviewRuleCode.VISUAL_ASSET_FILE_NOT_FOUND,
        title="素材文件无法读取",
        description="文件不存在（必需素材）",
        status=ReviewStatus.OPEN,
    )

    blockers = export_blocking_open_issues([issue])
    messages = critical_export_block_messages([issue], block_enabled=True)

    assert blockers == [issue]
    assert len(messages) == 1
    assert "素材文件无法读取" in messages[0]
