"""Phase N.2 — BackgroundJob queue, RBAC, CAD/BIM metadata."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from archium.application.background_job_service import BackgroundJobService
from archium.application.background_job_worker import BackgroundJobWorker
from archium.application.cad_bim_analysis import analyze_cad_bim_file
from archium.application.job_progress_service import JobProgressService
from archium.application.project_access_service import ProjectAccessService
from archium.domain.access import LOCAL_ACTOR_ID, ProjectPermission, ProjectRole
from archium.domain.background_job import BackgroundJobKind, BackgroundJobStatus
from archium.domain.enums import DocumentType
from archium.domain.job_progress import JobKind
from archium.domain.project import Project
from archium.exceptions import AccessDeniedError
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.document_parsers import get_parser_for_path
from archium.infrastructure.document_parsers._utils import infer_document_type


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import archium.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @contextmanager
    def _get_session():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    import archium.infrastructure.database.session as session_mod

    monkeypatch.setattr(session_mod, "get_session", _get_session)

    session = factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()
        engine.dispose()


def test_project_create_seeds_owner(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="RBAC 测试", description=""))
    members = ProjectAccessService(db_session).list_members(project.id)
    assert len(members) == 1
    assert members[0].actor_id == LOCAL_ACTOR_ID
    assert members[0].role == ProjectRole.OWNER


def test_rbac_client_cannot_edit(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="权限", description=""))
    access = ProjectAccessService(db_session)
    access.add_member(
        project.id,
        "client-1",
        ProjectRole.CLIENT,
        display_name="甲方",
        actor=LOCAL_ACTOR_ID,
    )
    assert access.can(project.id, "client-1", ProjectPermission.VIEW) is True
    assert access.can(project.id, "client-1", ProjectPermission.EDIT) is False
    with pytest.raises(AccessDeniedError):
        access.require(project.id, "client-1", ProjectPermission.EDIT)


def test_background_job_claim_and_complete_generic(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="Job", description=""))
    jobs = BackgroundJobService(db_session)
    queued = jobs.enqueue(
        project.id,
        BackgroundJobKind.GENERIC,
        label="noop",
        payload={"x": 1},
    )
    assert queued.status == BackgroundJobStatus.QUEUED

    done = BackgroundJobWorker(db_session).process_once()
    assert done is not None
    assert done.id == queued.id
    assert done.status == BackgroundJobStatus.COMPLETED
    assert done.result.get("acknowledged") is True

    progress = JobProgressService(db_session).list_for_project(project.id)
    kinds = {row.kind for row in progress}
    assert JobKind.BACKGROUND in kinds


def test_background_job_document_analyze_cad(db_session: Session, tmp_path: Path) -> None:
    ifc = tmp_path / "site.ifc"
    ifc.write_text("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
    project = ProjectRepository(db_session).create(Project(name="CAD Job", description=""))
    jobs = BackgroundJobService(db_session)
    jobs.enqueue(
        project.id,
        BackgroundJobKind.DOCUMENT_ANALYZE,
        label="analyze IFC",
        payload={"path": str(ifc)},
    )
    done = BackgroundJobWorker(db_session).process_once()
    assert done is not None
    assert done.status == BackgroundJobStatus.COMPLETED
    assert done.result.get("document_type") == DocumentType.IFC.value
    assert "CAD/BIM" in str(done.result.get("summary") or "")


def test_infer_and_parse_cad_bim(tmp_path: Path) -> None:
    dxf = tmp_path / "plan.dxf"
    dxf.write_text("0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n")
    assert infer_document_type(dxf) == DocumentType.DXF
    analysis = analyze_cad_bim_file(dxf)
    assert analysis.document_type == DocumentType.DXF
    assert analysis.as_metadata()["parse_depth"] == "metadata_only"

    parsed = get_parser_for_path(dxf).parse(dxf)
    assert "CAD/BIM" in parsed.text
    assert parsed.metadata.get("cad_bim") is True


def test_worker_cli_once_empty_queue(db_session: Session, monkeypatch) -> None:
    from contextlib import contextmanager

    from archium.workers.background import main, run_worker_loop

    @contextmanager
    def _sess():
        yield db_session

    import archium.workers.background as worker_mod

    monkeypatch.setattr(worker_mod, "get_session", _sess)
    assert run_worker_loop(once=True) == 0
    assert main(["--once"]) == 0


def test_ingestion_enqueues_cad_analyze(
    db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    from archium.application.ingestion_service import IngestionService
    from archium.config.settings import get_settings
    from archium.domain.background_job import BackgroundJobKind

    settings = get_settings()
    project = ProjectRepository(db_session).create(Project(name="CAD 导入", description=""))
    ifc = tmp_path / "model.ifc"
    ifc.write_text("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")

    # Avoid embedding / chromadb side effects for this unit path.
    service = IngestionService(db_session, settings=settings)
    monkeypatch.setattr(service, "_index_chunks", lambda *a, **k: None)
    monkeypatch.setattr(service, "_extract_facts_at_ingest", lambda *a, **k: None)
    monkeypatch.setattr(
        service,
        "_process_asset_vision_rag",
        lambda *a, **k: type(
            "R",
            (),
            {"assets": a[2] if len(a) > 2 else [], "chunks": []},
        )(),
    )

    result = service.import_file(project.id, ifc)
    assert result.error is None
    assert result.document is not None
    assert result.document.metadata.get("cad_analyze_queued") is True
    job_id = result.document.metadata.get("background_job_id")
    assert job_id

    jobs = BackgroundJobService(db_session).list_for_project(project.id)
    assert any(
        j.kind == BackgroundJobKind.DOCUMENT_ANALYZE and str(j.id) == job_id for j in jobs
    )


def test_project_invite_create_and_redeem(db_session: Session) -> None:
    from archium.application.project_invite_service import ProjectInviteService
    from archium.exceptions import ValidationError

    project = ProjectRepository(db_session).create(Project(name="邀请", description=""))
    invites = ProjectInviteService(db_session)
    invite = invites.create_invite(
        project.id,
        ProjectRole.REVIEWER,
        actor_id=LOCAL_ACTOR_ID,
        label="外部审阅",
        max_uses=2,
        ttl_hours=24,
    )
    assert invite.is_redeemable()
    assert len(invite.code) >= 6

    _, member = invites.redeem(invite.code, actor_id="guest-1", display_name="访客")
    assert member.role == ProjectRole.REVIEWER
    assert member.actor_id == "guest-1"

    refreshed = invites.get_by_code(invite.code)
    assert refreshed is not None
    assert refreshed.use_count == 1

    with pytest.raises(ValidationError):
        invites.create_invite(project.id, ProjectRole.OWNER, actor_id=LOCAL_ACTOR_ID)


def test_ifc_text_semantics_counts(tmp_path: Path) -> None:
    from archium.application.ifc_text_semantics import extract_ifc_text_semantics

    ifc = tmp_path / "building.ifc"
    ifc.write_text(
        "\n".join(
            [
                "ISO-10303-21;",
                "HEADER;",
                "FILE_SCHEMA(('IFC4'));",
                "ENDSEC;",
                "DATA;",
                "#1=IFCBUILDING('p1',$,'Main',$,$,$,$,$,$);",
                "#2=IFCBUILDINGSTOREY('s1',$,'L1',$,$,$,$,$,$);",
                "#3=IFCBUILDINGSTOREY('s2',$,'L2',$,$,$,$,$,$);",
                "#4=IFCSPACE('sp1',$,'Lobby',$,$,$,$,$,$);",
                "#5=IFCSPACE('sp2',$,'Office',$,$,$,$,$,$);",
                "#6=IFCWALLSTANDARDCASE('w1',$,$,$,$,$,$,$,$);",
                "#7=IFCDOOR('d1',$,$,$,$,$,$,$,$);",
                "ENDSEC;",
                "END-ISO-10303-21;",
            ]
        ),
        encoding="utf-8",
    )
    semantics = extract_ifc_text_semantics(ifc)
    assert semantics.schema == "IFC4"
    assert semantics.building_count == 1
    assert semantics.storey_count == 2
    assert semantics.space_count == 2
    assert semantics.wall_count == 1
    assert semantics.door_count == 1

    analysis = analyze_cad_bim_file(ifc)
    assert analysis.as_metadata()["parse_depth"] == "ifc_text_semantics"
    assert analysis.analysis.get("space_count") == 2
    assert "IFC schema" in "\n".join(analysis.notes)
