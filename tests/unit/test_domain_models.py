"""Tests for Archium domain models."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from archium.domain import (
    ApprovalStatus,
    Asset,
    AssetType,
    Chapter,
    Citation,
    DocumentChunk,
    DocumentType,
    Presentation,
    PresentationBrief,
    PresentationType,
    ProcessingStatus,
    Project,
    ProjectFact,
    ProjectStage,
    ProjectStatus,
    ProjectType,
    ReviewCategory,
    ReviewIssue,
    ReviewSeverity,
    SlideSpec,
    SlideStatus,
    SlideType,
    SourceDocument,
    Storyline,
    UserPreference,
    VerificationStatus,
    SlideVisualRequirement,
    VisualRequirement,
    VisualType,
)
from archium.domain._base import model_to_dict
from archium.domain.review_rules import ReviewRuleCode
from pydantic import ValidationError

SHA256 = "a" * 64
PROJECT_ID = uuid4()
PRESENTATION_ID = uuid4()
DOCUMENT_ID = uuid4()


def _citation(**overrides: object) -> Citation:
    defaults = {
        "document_id": DOCUMENT_ID,
        "document_name": "项目任务书.pdf",
        "page_number": 3,
        "confidence": 0.95,
    }
    defaults.update(overrides)
    return Citation(**defaults)  # type: ignore[arg-type]


class TestEnums:
    def test_project_type_values(self) -> None:
        assert ProjectType.HEALTHCARE == "healthcare"
        assert len(ProjectType) == 13

    def test_project_stage_values(self) -> None:
        assert ProjectStage.CONCEPT == "concept"
        assert len(ProjectStage) == 7

    def test_verification_status_values(self) -> None:
        assert set(VerificationStatus) == {
            VerificationStatus.EXTRACTED,
            VerificationStatus.INFERRED,
            VerificationStatus.USER_CONFIRMED,
            VerificationStatus.CONFLICTED,
            VerificationStatus.REJECTED,
        }

    def test_visual_type_values(self) -> None:
        assert VisualType.SITE_PLAN == "site_plan"
        assert VisualType.TEXT_ONLY == "text_only"

    def test_review_severity_values(self) -> None:
        assert ReviewSeverity.CRITICAL == "critical"
        assert ReviewSeverity.SUGGESTION == "suggestion"


class TestProject:
    def test_create_with_defaults(self) -> None:
        project = Project(name="某医院老院区更新")
        assert project.project_type == ProjectType.OTHER
        assert project.stage == ProjectStage.CONCEPT
        assert project.status == ProjectStatus.ACTIVE
        assert isinstance(project.id, UUID)

    def test_create_healthcare_project(self) -> None:
        project = Project(
            name="某医院老院区更新",
            project_type=ProjectType.HEALTHCARE,
            stage=ProjectStage.CONCEPT,
            location="上海",
        )
        assert project.project_type == ProjectType.HEALTHCARE

    def test_archive(self) -> None:
        project = Project(name="测试项目")
        project.archive()
        assert project.status == ProjectStatus.ARCHIVED

    def test_serialization_roundtrip(self) -> None:
        project = Project(name="测试", code="PRJ-001")
        data = model_to_dict(project)
        restored = Project.model_validate(data)
        assert restored.name == project.name
        assert restored.id == project.id


class TestSourceDocument:
    def test_valid_document(self) -> None:
        doc = SourceDocument(
            project_id=PROJECT_ID,
            filename="项目任务书.pdf",
            original_path="/uploads/项目任务书.pdf",
            stored_path="data/projects/x/sources/项目任务书.pdf",
            file_type=DocumentType.PDF,
            file_hash=SHA256,
            size_bytes=1024,
            page_count=12,
        )
        assert doc.processing_status == ProcessingStatus.PENDING

    def test_invalid_hash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="file_hash"):
            SourceDocument(
                project_id=PROJECT_ID,
                filename="bad.pdf",
                original_path="/bad.pdf",
                stored_path="/stored/bad.pdf",
                file_type=DocumentType.PDF,
                file_hash="not-a-hash",
                size_bytes=100,
            )

    def test_mark_completed(self) -> None:
        doc = SourceDocument(
            project_id=PROJECT_ID,
            filename="test.pdf",
            original_path="/test.pdf",
            stored_path="/stored/test.pdf",
            file_type=DocumentType.PDF,
            file_hash=SHA256,
            size_bytes=100,
        )
        doc.mark_completed(page_count=5)
        assert doc.processing_status == ProcessingStatus.COMPLETED
        assert doc.page_count == 5


class TestDocumentChunk:
    def test_create_chunk(self) -> None:
        chunk = DocumentChunk(
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
            content="院区现状存在交通组织混乱问题。",
            page_number=2,
            chunk_index=0,
        )
        assert chunk.content_type == "text"


class TestProjectFact:
    def test_extracted_fact(self) -> None:
        fact = ProjectFact(
            project_id=PROJECT_ID,
            key="site_area",
            label="用地面积",
            value=12000,
            unit="㎡",
            category="site",
            verification_status=VerificationStatus.EXTRACTED,
            source_citations=[_citation(quote="用地面积约 1.2 公顷")],
        )
        assert fact.key == "site_area"
        assert not fact.is_confirmed
        assert not fact.is_inferred

    def test_inferred_fact(self) -> None:
        fact = ProjectFact(
            project_id=PROJECT_ID,
            key="floor_count",
            label="层数",
            value=8,
            verification_status=VerificationStatus.INFERRED,
        )
        assert fact.is_inferred

    def test_confirm_and_reject(self) -> None:
        fact = ProjectFact(
            project_id=PROJECT_ID,
            key="budget",
            label="预算",
            value="未知",
        )
        fact.confirm()
        assert fact.is_confirmed
        fact.reject()
        assert fact.verification_status == VerificationStatus.REJECTED

    def test_key_normalization(self) -> None:
        fact = ProjectFact(
            project_id=PROJECT_ID,
            key="Site Area",
            label="用地面积",
            value=100,
        )
        assert fact.key == "site_area"


class TestPresentationBrief:
    def test_create_brief(self) -> None:
        brief = PresentationBrief(
            project_id=PROJECT_ID,
            presentation_id=PRESENTATION_ID,
            title="老院区更新概念汇报",
            presentation_type=PresentationType.CLIENT_REVIEW,
            audience="医院管理层",
            purpose="确认总体改造方向",
            duration_minutes=20,
            target_slide_count=20,
            core_message="以交通重组、立面更新和公共空间提升改善老院区整体体验",
            required_sections=["现状分析", "改造策略", "实施路径"],
        )
        assert brief.version == 1
        assert brief.approval_status == ApprovalStatus.DRAFT
        assert brief.language == "zh-CN"

    def test_approve_brief(self) -> None:
        brief = PresentationBrief(
            project_id=PROJECT_ID,
            presentation_id=PRESENTATION_ID,
            title="汇报",
            audience="管理层",
            purpose="决策",
            core_message="核心观点",
        )
        brief.approve()
        assert brief.approval_status == ApprovalStatus.APPROVED


class TestStoryline:
    def test_create_storyline(self) -> None:
        chapters = [
            Chapter(
                id="ch1",
                title="现状与问题",
                purpose="建立改造必要性",
                key_message="交通与公共空间是核心痛点",
                order=0,
                estimated_slide_count=4,
            ),
            Chapter(
                id="ch2",
                title="改造策略",
                purpose="提出总体方向",
                key_message="交通重组带动整体品质提升",
                order=1,
                estimated_slide_count=8,
            ),
        ]
        storyline = Storyline(
            presentation_id=PRESENTATION_ID,
            thesis="通过交通重组与空间更新改善老院区体验",
            chapters=chapters,
        )
        assert len(storyline.chapters) == 2

    def test_duplicate_chapter_order_rejected(self) -> None:
        chapters = [
            Chapter(
                id="ch1",
                title="A",
                purpose="p",
                key_message="m",
                order=0,
            ),
            Chapter(
                id="ch2",
                title="B",
                purpose="p",
                key_message="m",
                order=0,
            ),
        ]
        with pytest.raises(ValidationError, match="unique"):
            Storyline(presentation_id=PRESENTATION_ID, thesis="test", chapters=chapters)


class TestSlideSpec:
    def test_create_slide(self) -> None:
        slide = SlideSpec(
            presentation_id=PRESENTATION_ID,
            chapter_id="ch1",
            order=0,
            title="院区现状",
            message="现有交通组织无法满足医院日常运营需求",
            slide_type=SlideType.CONTENT,
            key_points=["人车混行", "落客区不足", "消防通道被占用"],
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图标注交通流线",
                    required=True,
                )
            ],
            source_citations=[_citation()],
        )
        assert slide.status == SlideStatus.PLANNED

    def test_message_must_be_single_conclusion(self) -> None:
        with pytest.raises(ValidationError, match="single core conclusion"):
            SlideSpec(
                presentation_id=PRESENTATION_ID,
                chapter_id="ch1",
                order=0,
                title="过长",
                message="第一点。第二点。第三点。第四点。",
            )

    def test_key_points_max_five(self) -> None:
        with pytest.raises(ValidationError, match="5 items"):
            SlideSpec(
                presentation_id=PRESENTATION_ID,
                chapter_id="ch1",
                order=0,
                title="测试",
                message="核心观点",
                key_points=["1", "2", "3", "4", "5", "6"],
            )


class TestAsset:
    def test_create_asset(self) -> None:
        asset = Asset(
            project_id=PROJECT_ID,
            filename="总平面图.jpg",
            path="data/projects/x/assets/总平面图.jpg",
            asset_type=AssetType.IMAGE,
            width=4000,
            height=3000,
            tags=["site_plan", "master_plan"],
        )
        assert asset.aspect_ratio == pytest.approx(4000 / 3000)
        assert not asset.is_low_resolution

    def test_low_resolution_detection(self) -> None:
        asset = Asset(
            project_id=PROJECT_ID,
            filename="small.jpg",
            path="/small.jpg",
            width=640,
            height=480,
        )
        assert asset.is_low_resolution


class TestReviewIssue:
    def test_create_issue(self) -> None:
        issue = ReviewIssue(
            presentation_id=PRESENTATION_ID,
            category=ReviewCategory.CITATION,
            severity=ReviewSeverity.HIGH,
            rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
            title="缺少来源引用",
            description="用地面积数据未关联文档来源",
        )
        assert issue.status.value == "open"

    def test_resolve_issue(self) -> None:
        issue = ReviewIssue(
            presentation_id=PRESENTATION_ID,
            category=ReviewCategory.CONTENT,
            severity=ReviewSeverity.MEDIUM,
            rule_code=ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS,
            title="文字过多",
            description="该页超过 5 条要点",
        )
        issue.resolve()
        assert issue.status.value == "resolved"

    def test_legacy_payload_infers_rule_code_from_title(self) -> None:
        issue = ReviewIssue.model_validate(
            {
                "presentation_id": str(PRESENTATION_ID),
                "category": ReviewCategory.CITATION.value,
                "severity": ReviewSeverity.HIGH.value,
                "title": "缺少引用来源",
                "description": "未关联项目资料。",
            }
        )
        assert issue.rule_code == ReviewRuleCode.EVIDENCE_MISSING_CITATION


class TestUserPreference:
    def test_create_preference(self) -> None:
        pref = UserPreference(key="default_language", value="zh-CN")
        assert pref.project_id is None

    def test_project_scoped_preference(self) -> None:
        pref = UserPreference(
            key="preferred_tone",
            value="formal",
            project_id=PROJECT_ID,
        )
        assert pref.project_id == PROJECT_ID


class TestPresentation:
    def test_create_presentation(self) -> None:
        pres = Presentation(
            project_id=PROJECT_ID,
            title="老院区更新概念汇报",
        )
        assert pres.status.value == "draft"


class TestJsonSerialization:
    """Golden-style serialization tests for all core models."""

    @pytest.mark.parametrize(
        "model",
        [
            Project(name="测试项目", project_type=ProjectType.HEALTHCARE),
            SourceDocument(
                project_id=PROJECT_ID,
                filename="test.pdf",
                original_path="/test.pdf",
                stored_path="/stored/test.pdf",
                file_type=DocumentType.PDF,
                file_hash=SHA256,
                size_bytes=100,
            ),
            ProjectFact(
                project_id=PROJECT_ID,
                key="area",
                label="面积",
                value=1000,
            ),
            PresentationBrief(
                project_id=PROJECT_ID,
                presentation_id=PRESENTATION_ID,
                title="汇报",
                audience="甲方",
                purpose="决策",
                core_message="核心信息",
            ),
            SlideSpec(
                presentation_id=PRESENTATION_ID,
                chapter_id="ch1",
                order=0,
                title="标题",
                message="单一核心观点",
            ),
        ],
    )
    def test_json_roundtrip(self, model: object) -> None:
        from pydantic import BaseModel

        assert isinstance(model, BaseModel)
        json_str = json.dumps(model.model_dump(mode="json"))
        restored = type(model).model_validate(json.loads(json_str))
        assert restored.model_dump() == model.model_dump()
