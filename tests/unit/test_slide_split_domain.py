"""Domain-level tests for automated slide split (拆页) during layout repair."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from archium.application.slide_diff import slide_to_snapshot
from archium.application.slide_history_service import SlideHistoryService
from archium.application.slide_repair_policy import (
    _build_split_slide,
    apply_tiered_layout_repair,
    insert_split_slide,
)
from archium.application.slide_repair_service import SlideRepairService
from archium.config.settings import Settings
from archium.domain.citation import Citation
from archium.domain.asset import Asset
from archium.domain.enums import (
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    AssetType,
    SlideChangeSource,
    SlideRepairTier,
    SlideStatus,
    SlideType,
    VisualType,
)
from archium.domain.presentation import Chapter, Presentation, Storyline
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec, VisualRequirement, build_slide_logical_key
from archium.domain.slide_repair import SlideRepairRecord
from archium.infrastructure.database.models import SlideORM
from archium.infrastructure.database.repositories import (
    AssetRepository,
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


def _citation(*, name: str = "交通专项规划.pdf") -> Citation:
    return Citation(
        document_id=uuid4(),
        document_name=name,
        page_number=12,
        chunk_id=uuid4(),
        quote="人车混行比例 35%",
    )


def _split_trigger_slide(**overrides: object) -> SlideSpec:
    defaults: dict[str, object] = {
        "presentation_id": uuid4(),
        "chapter_id": "ch-traffic",
        "order": 1,
        "title": "交通组织",
        "message": "人车混行导致通行效率低。",
        "slide_type": SlideType.CONTENT,
        "status": SlideStatus.PLANNED,
        "key_points": [f"现状要点 {index}" for index in range(6)],
        "source_citations": [_citation()],
        "speaker_notes": "讲解时强调现状问题与改造必要性",
        "visual_requirements": [
            VisualRequirement(
                type=VisualType.DIAGRAM,
                description="交通流线示意",
                required=True,
            )
        ],
    }
    defaults.update(overrides)
    return SlideSpec.model_construct(**defaults)  # type: ignore[arg-type]


def _slides_for_order_test(presentation_id: UUID) -> list[SlideSpec]:
    return [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch-traffic",
            order=0,
            title="封面",
            message="项目背景概述。",
            slide_type=SlideType.SECTION,
            status=SlideStatus.PLANNED,
        ),
        _split_trigger_slide(presentation_id=presentation_id, order=1),
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch-traffic",
            order=2,
            title="改造策略",
            message="通过交通重组释放空间。",
            slide_type=SlideType.CONTENT,
            status=SlideStatus.PLANNED,
        ),
    ]


def _load_slide_raw(db_session: Session, slide_id: UUID) -> SlideSpec:
    """Load a slide without re-validating key-point count (pre-repair violations)."""
    orm = db_session.get(SlideORM, slide_id)
    assert orm is not None
    from archium.infrastructure.database import mappers

    return SlideSpec.model_construct(
        id=orm.id,
        presentation_id=orm.presentation_id,
        lineage_id=orm.lineage_id,
        logical_key=orm.logical_key,
        chapter_id=orm.chapter_id,
        order=orm.order,
        title=orm.title,
        message=orm.message,
        slide_type=SlideType(orm.slide_type),
        layout_id=orm.layout_id,
        key_points=list(orm.key_points_json or []),
        visual_requirements=mappers.visual_requirements_from_json(
            orm.visual_requirements_json or []
        ),
        source_citations=mappers.citations_from_json(orm.source_citations_json or []),
        speaker_notes=orm.speaker_notes,
        status=SlideStatus(orm.status),
        version=orm.version,
    )


@pytest.fixture
def split_presentation(db_session: Session) -> tuple[UUID, list[SlideSpec], Storyline]:
    project = ProjectRepository(db_session).create(Project(name="拆页测试项目"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="拆页测试")
    )
    storyline = Storyline(
        presentation_id=presentation.id,
        thesis="交通重组是改造核心",
        chapters=[
            Chapter(
                id="ch-traffic",
                title="交通组织",
                purpose="说明现状问题",
                key_message="人车冲突严重",
                order=0,
                estimated_slide_count=4,
            )
        ],
    )
    PresentationRepository(db_session).save_storyline(storyline)
    pres_repo = PresentationRepository(db_session)
    saved_slides: list[SlideSpec] = []
    for slide in _slides_for_order_test(presentation.id):
        if slide.order == 1:
            saved = pres_repo.save_slide(
                slide.model_copy(update={"key_points": slide.key_points[:5]})
            )
            orm = db_session.get(SlideORM, saved.id)
            assert orm is not None
            orm.key_points_json = slide.key_points
            db_session.flush()
            saved_slides.append(_load_slide_raw(db_session, saved.id))
        else:
            saved_slides.append(pres_repo.save_slide(slide))
    SlideHistoryService(db_session).record_snapshot(
        saved_slides[1],
        SlideChangeSource.GENERATED,
        note="拆页前基线",
    )
    return presentation.id, saved_slides, storyline


def _layout_issue(presentation_id: UUID, slide_id: UUID) -> ReviewIssue:
    return ReviewIssue(
        presentation_id=presentation_id,
        slide_id=slide_id,
        reviewer_layer=ReviewLayer.LAYOUT,
        category=ReviewCategory.LENGTH,
        severity=ReviewSeverity.MEDIUM,
        rule_code=ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS,
        title="要点过多",
        description="第 2 页要点超过 5 条",
        auto_fixable=True,
    )


def _list_slides_raw(db_session: Session, presentation_id: UUID) -> list[SlideSpec]:
    stmt = (
        select(SlideORM)
        .where(SlideORM.presentation_id == presentation_id)
        .order_by(SlideORM.order)
    )
    return [_load_slide_raw(db_session, row.id) for row in db_session.scalars(stmt)]


def _restore_slide_raw(
    db_session: Session,
    slide_id: UUID,
    *,
    message: str,
    key_points: list[str],
) -> None:
    orm = db_session.get(SlideORM, slide_id)
    assert orm is not None
    orm.message = message
    orm.key_points_json = list(key_points)
    db_session.flush()


def _undo_slide_split(
    db_session: Session,
    repair_record: SlideRepairRecord,
) -> list[SlideSpec]:
    """Revert a split using the repair audit record and standard repository operations."""
    pres_repo = PresentationRepository(db_session)
    original = _load_slide_raw(db_session, repair_record.slide_id)
    assert original is not None

    _restore_slide_raw(
        db_session,
        repair_record.slide_id,
        message=repair_record.before_message,
        key_points=list(repair_record.before_key_points),
    )

    split_id = repair_record.split_slide_id
    if split_id is None:
        return _list_slides_raw(db_session, repair_record.presentation_id)

    split_slide = pres_repo.get_slide(split_id)
    assert split_slide is not None
    split_order = split_slide.order
    db_session.delete(db_session.get(SlideORM, split_id))
    db_session.flush()

    for slide in _list_slides_raw(db_session, repair_record.presentation_id):
        if slide.order > split_order:
            pres_repo.save_slide(
                slide.model_copy(
                    update={
                        "order": slide.order - 1,
                        "logical_key": build_slide_logical_key(
                            slide.chapter_id,
                            slide.order - 1,
                        ),
                    }
                )
            )

    return _list_slides_raw(db_session, repair_record.presentation_id)


class TestSplitSlidePolicy:
    def test_build_split_slide_preserves_chapter_and_allocates_citations(self) -> None:
        citation = _citation()
        slide = _split_trigger_slide(source_citations=[citation])
        moved = ["床位规模 500 张", "要点 6"]

        split = _build_split_slide(slide, moved)

        assert split.chapter_id == slide.chapter_id
        assert split.order == slide.order + 1
        assert split.logical_key == build_slide_logical_key(slide.chapter_id, split.order)
        assert split.title.endswith("补充说明") or split.title.endswith("（续）")
        assert split.key_points == moved
        assert split.source_citations == [citation]
        assert split.visual_requirements
        assert split.speaker_notes is None

    def test_build_split_slide_omits_citations_when_moved_points_are_generic(self) -> None:
        citation = _citation()
        slide = _split_trigger_slide(source_citations=[citation])
        moved = ["补充说明", "其他背景"]

        split = _build_split_slide(slide, moved)

        assert split.source_citations == []
        assert slide.source_citations == [citation]

    def test_insert_split_slide_renumbers_orders_and_logical_keys(self) -> None:
        presentation_id = uuid4()
        slides = [
            SlideSpec(
                presentation_id=presentation_id,
                chapter_id="ch1",
                order=0,
                title="A",
                message="A",
                slide_type=SlideType.CONTENT,
            ),
            SlideSpec(
                presentation_id=presentation_id,
                chapter_id="ch1",
                order=1,
                title="B",
                message="B",
                slide_type=SlideType.CONTENT,
            ),
            SlideSpec(
                presentation_id=presentation_id,
                chapter_id="ch1",
                order=2,
                title="C",
                message="C",
                slide_type=SlideType.CONTENT,
            ),
        ]
        split = _build_split_slide(slides[1], ["溢出要点"])

        merged = insert_split_slide(slides, split)

        assert [slide.order for slide in merged] == [0, 1, 2, 3]
        assert merged[1].title == "B"
        assert merged[2].title.startswith("B")
        assert merged[3].title == "C"
        assert merged[3].logical_key == build_slide_logical_key("ch1", 3)


class TestSplitSlideService:
    def test_split_repair_is_domain_operation_not_string_truncation(
        self,
        db_session: Session,
        split_presentation: tuple[UUID, list[SlideSpec], Storyline],
    ) -> None:
        presentation_id, seeded_slides, storyline = split_presentation
        target = seeded_slides[1]
        original_lineage = target.lineage_id
        issue = ReviewRepository(db_session).create(
            _layout_issue(presentation_id, target.id)
        )

        slides, repaired, records = SlideRepairService(
            db_session,
            llm=None,
            settings=Settings(_env_file=None, slide_repair_enabled=False),
        ).repair_slides(presentation_id, seeded_slides, [issue], storyline=storyline)

        assert repaired == 1
        assert len(records) == 1
        record = records[0]
        assert record.tier == SlideRepairTier.SPLIT
        assert record.split_slide_id is not None

        persisted = PresentationRepository(db_session).list_slides(presentation_id)
        original = next(slide for slide in persisted if slide.id == target.id)
        split_slide = next(slide for slide in persisted if slide.id == record.split_slide_id)

        assert len(original.key_points) <= 5
        assert len(split_slide.key_points) >= 1
        assert original.key_points + split_slide.key_points == target.key_points
        assert original_lineage == target.lineage_id
        assert split_slide.lineage_id != original.lineage_id

    def test_split_preserves_citations_speaker_notes_and_visuals_on_original(
        self,
        db_session: Session,
        split_presentation: tuple[UUID, list[SlideSpec], Storyline],
    ) -> None:
        presentation_id, seeded_slides, storyline = split_presentation
        target = seeded_slides[1]
        issue = ReviewRepository(db_session).create(
            _layout_issue(presentation_id, target.id)
        )

        SlideRepairService(
            db_session,
            llm=None,
            settings=Settings(_env_file=None, slide_repair_enabled=False),
        ).repair_slides(presentation_id, seeded_slides, [issue], storyline=storyline)

        persisted = PresentationRepository(db_session).list_slides(presentation_id)
        original = next(slide for slide in persisted if slide.id == target.id)
        split_slide = next(
            slide for slide in persisted if slide.id != target.id and slide.order == target.order + 1
        )

        assert original.source_citations
        assert original.speaker_notes == target.speaker_notes
        assert original.visual_requirements
        assert original.visual_requirements[0].type == VisualType.DIAGRAM
        assert {citation.document_id for citation in original.source_citations} == {
            citation.document_id for citation in target.source_citations
        }
        if split_slide.source_citations:
            assert {
                citation.document_id for citation in split_slide.source_citations
            }.issubset({citation.document_id for citation in target.source_citations})

    def test_split_rematch_assets_for_continuation_slide(
        self,
        db_session: Session,
        split_presentation: tuple[UUID, list[SlideSpec], Storyline],
    ) -> None:
        presentation_id, seeded_slides, storyline = split_presentation
        project_id = ProjectRepository(db_session).list_all()[0].id
        diagram_asset = AssetRepository(db_session).create(
            Asset(
                project_id=project_id,
                filename="traffic_flow.png",
                path="/tmp/traffic_flow.png",
                asset_type=AssetType.DIAGRAM,
                description="交通流线示意",
                tags=["diagram", "traffic"],
                quality_score=0.9,
            )
        )
        target = seeded_slides[1]
        issue = ReviewRepository(db_session).create(
            _layout_issue(presentation_id, target.id)
        )

        SlideRepairService(
            db_session,
            llm=None,
            settings=Settings(_env_file=None, slide_repair_enabled=False),
        ).repair_slides(
            presentation_id,
            seeded_slides,
            [issue],
            storyline=storyline,
            project_id=project_id,
        )

        persisted = PresentationRepository(db_session).list_slides(presentation_id)
        split_slide = next(
            slide for slide in persisted if slide.id != target.id and slide.order == target.order + 1
        )

        assert split_slide.visual_requirements
        assert split_slide.visual_requirements[0].preferred_asset_ids == [diagram_asset.id]

    def test_split_renumbers_subsequent_slides_and_updates_chapter_slide_count(
        self,
        db_session: Session,
        split_presentation: tuple[UUID, list[SlideSpec], Storyline],
    ) -> None:
        presentation_id, seeded_slides, storyline = split_presentation
        target = seeded_slides[1]
        trailing = seeded_slides[2]
        issue = ReviewRepository(db_session).create(
            _layout_issue(presentation_id, target.id)
        )

        SlideRepairService(
            db_session,
            llm=None,
            settings=Settings(_env_file=None, slide_repair_enabled=False),
        ).repair_slides(presentation_id, seeded_slides, [issue], storyline=storyline)

        persisted = PresentationRepository(db_session).list_slides(presentation_id)
        assert [slide.order for slide in persisted] == [0, 1, 2, 3]
        assert persisted[0].logical_key == build_slide_logical_key("ch-traffic", 0)
        assert persisted[3].id == trailing.id
        assert persisted[3].order == 3
        assert persisted[3].logical_key == build_slide_logical_key("ch-traffic", 3)

        chapter_slides = [slide for slide in persisted if slide.chapter_id == "ch-traffic"]
        assert len(chapter_slides) == 4
        assert storyline.chapters[0].estimated_slide_count == 4

    def test_split_records_before_and_after_history(
        self,
        db_session: Session,
        split_presentation: tuple[UUID, list[SlideSpec], Storyline],
    ) -> None:
        presentation_id, seeded_slides, storyline = split_presentation
        target = seeded_slides[1]
        history = SlideHistoryService(db_session)
        issue = ReviewRepository(db_session).create(
            _layout_issue(presentation_id, target.id)
        )

        _, _, records = SlideRepairService(
            db_session,
            llm=None,
            settings=Settings(_env_file=None, slide_repair_enabled=False),
        ).repair_slides(presentation_id, seeded_slides, [issue], storyline=storyline)
        record = records[0]
        assert record.split_slide_id is not None

        original_revisions = history.list_revisions_by_lineage(target.lineage_id)
        split_revisions = history.list_revisions_by_lineage(
            PresentationRepository(db_session).get_slide(record.split_slide_id).lineage_id  # type: ignore[union-attr]
        )

        assert len(original_revisions) >= 2
        baseline = next(
            revision
            for revision in reversed(original_revisions)
            if revision.change_source == SlideChangeSource.GENERATED
        )
        repair_revision = next(
            revision
            for revision in original_revisions
            if revision.change_source == SlideChangeSource.AUTO_REPAIR
        )
        assert baseline.snapshot["key_points"] == slide_to_snapshot(target)["key_points"]
        assert repair_revision.note
        assert "拆分" in repair_revision.note or "溢出" in repair_revision.note

        diff = history.diff_revisions(baseline.id, repair_revision.id)
        assert diff.has_changes
        assert any(change.field == "key_points" for change in diff.changes)

        assert len(split_revisions) == 1
        assert split_revisions[0].change_source == SlideChangeSource.AUTO_REPAIR
        assert split_revisions[0].note == "由版面拆分自动创建"

    def test_user_can_undo_split_via_repair_audit_record(
        self,
        db_session: Session,
        split_presentation: tuple[UUID, list[SlideSpec], Storyline],
    ) -> None:
        presentation_id, seeded_slides, storyline = split_presentation
        target = seeded_slides[1]
        trailing = seeded_slides[2]
        issue = ReviewRepository(db_session).create(
            _layout_issue(presentation_id, target.id)
        )

        slides, _, records = SlideRepairService(
            db_session,
            llm=None,
            settings=Settings(_env_file=None, slide_repair_enabled=False),
        ).repair_slides(presentation_id, seeded_slides, [issue], storyline=storyline)
        record = records[0]
        assert record.split_slide_id is not None
        assert len(slides) == 4

        restored_slides = _undo_slide_split(db_session, record)

        assert len(restored_slides) == 3
        assert [slide.order for slide in restored_slides] == [0, 1, 2]
        original = next(slide for slide in restored_slides if slide.id == target.id)
        assert original.key_points == target.key_points
        assert original.message == target.message
        assert restored_slides[2].id == trailing.id
        assert restored_slides[2].order == 2
        assert PresentationRepository(db_session).get_slide(record.split_slide_id) is None


def test_overflow_split_via_policy_keeps_all_key_points_in_presentation() -> None:
    slide = SlideSpec.model_construct(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="测试页",
        message="总体改造方向",
        slide_type=SlideType.CONTENT,
        status=SlideStatus.PLANNED,
        key_points=[f"要点 {index}" for index in range(6)],
    )
    outcome = apply_tiered_layout_repair(slide)

    assert outcome.split_slide is not None
    combined = outcome.slide.key_points + outcome.split_slide.key_points
    assert combined == slide.key_points
