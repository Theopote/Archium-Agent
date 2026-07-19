"""Tests for Studio asset reference integrity checks."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.visual.asset_reference import (
    AssetReferenceResolver,
    assert_studio_asset_reference,
)
from archium.config import get_settings
from archium.domain.asset import Asset
from archium.domain.document import SourceDocument
from archium.domain.enums import AssetType, ProcessingStatus, SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.studio_errors import (
    STUDIO_ASSET_FILE_MISSING,
    STUDIO_ASSET_NOT_FOUND,
    STUDIO_ASSET_PROJECT_MISMATCH,
    STUDIO_ASSET_TYPE_INCOMPATIBLE,
    STUDIO_DRAWING_REPLACED_BY_PHOTO,
    StudioAssetReferenceError,
)
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.database.repositories import (
    AssetRepository,
    DocumentRepository,
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _drawing_element() -> LayoutElement:
    return LayoutElement(
        id="drawing",
        role=LayoutElementRole.HERO_VISUAL,
        content_type=LayoutContentType.DRAWING,
        x=1,
        y=1,
        width=8,
        height=4,
    )


def test_assert_rejects_unknown_asset_id(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="Asset test"))
    with pytest.raises(StudioAssetReferenceError) as exc:
        assert_studio_asset_reference(
            db_session,
            project_id=project.id,
            content_ref=str(uuid4()),
            element=_drawing_element(),
            settings=get_settings(),
        )
    assert exc.value.code == STUDIO_ASSET_NOT_FOUND


def test_assert_rejects_cross_project_asset(
    db_session: Session,
    tmp_path: Path,
) -> None:
    owner = ProjectRepository(db_session).create(Project(name="Owner"))
    other = ProjectRepository(db_session).create(Project(name="Other"))
    asset_path = tmp_path / "hero.png"
    asset_path.write_bytes(b"png")
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=other.id,
            filename="hero.png",
            path=str(asset_path),
            asset_type=AssetType.DRAWING,
        )
    )
    db_session.commit()

    with pytest.raises(StudioAssetReferenceError) as exc:
        assert_studio_asset_reference(
            db_session,
            project_id=owner.id,
            content_ref=str(asset.id),
            element=_drawing_element(),
            settings=get_settings(),
        )
    assert exc.value.code == STUDIO_ASSET_PROJECT_MISMATCH


def test_assert_rejects_missing_file(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="Missing file"))
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            filename="missing.png",
            path="assets/does-not-exist.png",
            asset_type=AssetType.DRAWING,
        )
    )
    db_session.commit()

    with pytest.raises(StudioAssetReferenceError) as exc:
        assert_studio_asset_reference(
            db_session,
            project_id=project.id,
            content_ref=str(asset.id),
            element=_drawing_element(),
            settings=get_settings(),
        )
    assert exc.value.code == STUDIO_ASSET_FILE_MISSING


def test_assert_rejects_unsupported_format(
    db_session: Session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Format"))
    asset_path = tmp_path / "detail.bmp"
    asset_path.write_bytes(b"bmp")
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            filename="detail.bmp",
            path=str(asset_path),
            asset_type=AssetType.DRAWING,
        )
    )
    db_session.commit()

    with pytest.raises(StudioAssetReferenceError) as exc:
        assert_studio_asset_reference(
            db_session,
            project_id=project.id,
            content_ref=str(asset.id),
            element=_drawing_element(),
            settings=get_settings(),
        )
    assert exc.value.code == STUDIO_ASSET_TYPE_INCOMPATIBLE


def test_assert_rejects_photo_on_drawing_slot(
    db_session: Session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Photo on drawing"))
    asset_path = tmp_path / "photo.png"
    asset_path.write_bytes(b"png")
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            filename="photo.png",
            path=str(asset_path),
            asset_type=AssetType.PHOTO,
        )
    )
    db_session.commit()

    with pytest.raises(StudioAssetReferenceError) as exc:
        assert_studio_asset_reference(
            db_session,
            project_id=project.id,
            content_ref=str(asset.id),
            element=_drawing_element(),
            settings=get_settings(),
        )
    assert exc.value.code == STUDIO_DRAWING_REPLACED_BY_PHOTO


def test_assert_accepts_valid_drawing_asset(
    db_session: Session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Valid"))
    asset_path = tmp_path / "plan.png"
    asset_path.write_bytes(b"png")
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            filename="plan.png",
            path=str(asset_path),
            asset_type=AssetType.DRAWING,
        )
    )
    db_session.commit()

    resolved = AssetReferenceResolver(db_session).resolve(
        project_id=project.id,
        content_ref=str(asset.id),
        element=_drawing_element(),
    )
    assert resolved.ref == str(asset.id)
    assert resolved.resolved_path.is_file()


def test_assert_rejects_asset_while_document_processing(
    db_session: Session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Processing"))
    document = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="scan.pdf",
            original_path=str(tmp_path / "scan.pdf"),
            stored_path=str(tmp_path / "scan.pdf"),
            file_type="pdf",
            file_hash="a" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.PROCESSING,
        )
    )
    asset_path = tmp_path / "page.png"
    asset_path.write_bytes(b"png")
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=document.id,
            filename="page.png",
            path=str(asset_path),
            asset_type=AssetType.DRAWING,
        )
    )
    db_session.commit()

    with pytest.raises(StudioAssetReferenceError) as exc:
        assert_studio_asset_reference(
            db_session,
            project_id=project.id,
            content_ref=str(asset.id),
            element=_drawing_element(),
            settings=get_settings(),
        )
    assert exc.value.code == STUDIO_ASSET_FILE_MISSING


def test_set_element_asset_rejects_invalid_ref(db_session: Session, tmp_path: Path) -> None:
    from archium.application.visual.visual_edit_service import VisualEditService

    project = ProjectRepository(db_session).create(Project(name="Edit"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="Deck")
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="Page",
            message="Msg",
            slide_type=SlideType.CONTENT,
        )
    )
    plan = LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        hero_element_id="hero",
        reading_order=["hero"],
        whitespace_ratio=0.3,
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=8,
                height=3,
            )
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    from archium.infrastructure.database.visual_repositories import LayoutPlanRepository

    saved = LayoutPlanRepository(db_session).save(plan)
    slide.layout_plan_id = saved.id
    PresentationRepository(db_session).save_slide(slide)
    db_session.commit()

    service = VisualEditService(db_session)
    with pytest.raises(StudioAssetReferenceError) as exc:
        service.apply_intent(
            slide.id,
            "set_element_asset",
            params={"element_id": "hero", "content_ref": str(uuid4())},
        )
    assert exc.value.code == STUDIO_ASSET_NOT_FOUND
