"""Topic 05 Phase M3 — IFC/CAD text → world-model spatial facts."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.background_job_service import BackgroundJobService
from archium.application.background_job_worker import BackgroundJobWorker
from archium.application.cad_bim_analysis import analyze_cad_bim_file
from archium.application.cad_spatial_fact_materializer import materialize_cad_spatial_facts
from archium.application.ifc_text_semantics import extract_ifc_text_semantics
from archium.application.visual_evidence_service import build_visual_evidence_pack
from archium.domain.background_job import BackgroundJobKind
from archium.domain.document import SourceDocument
from archium.domain.enums import DocumentType, ProcessingStatus, ProjectType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _sample_ifc(tmp_path: Path) -> Path:
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
    return ifc


def test_ifc_name_harvest(tmp_path: Path) -> None:
    semantics = extract_ifc_text_semantics(_sample_ifc(tmp_path))
    assert "Lobby" in semantics.space_names
    assert "Office" in semantics.space_names
    assert "L1" in semantics.storey_names
    assert "Main" in semantics.building_names


def test_materialize_ifc_facts_into_ledger(
    db_session: Session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="IFC事实项目", project_type=ProjectType.CULTURE)
    )
    ifc = _sample_ifc(tmp_path)
    analysis = analyze_cad_bim_file(ifc)
    document = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename=ifc.name,
            original_path=str(ifc),
            stored_path=str(ifc),
            file_type=DocumentType.IFC,
            file_hash="1" * 64,
            size_bytes=ifc.stat().st_size,
            processing_status=ProcessingStatus.COMPLETED,
            metadata=analysis.as_metadata(),
        )
    )
    created = materialize_cad_spatial_facts(
        db_session, project.id, document, analysis=analysis
    )
    assert created >= 1
    facts = {f.key: f for f in FactRepository(db_session).list_by_project(project.id)}
    assert facts["floors"].value == "2"
    assert "Lobby" in str(facts["constraints"].value)
    assert "Office" in str(facts.get("main_function").value)

    pack = build_visual_evidence_pack(db_session, project.id)
    assert pack.cad_bim_count >= 1
    assert any(line.startswith("cad_bim:") for line in pack.input_source_lines())


def test_document_analyze_writes_back_and_facts(
    db_session: Session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="CAD任务项目", project_type=ProjectType.CULTURE)
    )
    ifc = _sample_ifc(tmp_path)
    document = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename=ifc.name,
            original_path=str(ifc),
            stored_path=str(ifc),
            file_type=DocumentType.IFC,
            file_hash="2" * 64,
            size_bytes=ifc.stat().st_size,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={"cad_bim": True},
        )
    )
    BackgroundJobService(db_session).enqueue(
        project.id,
        BackgroundJobKind.DOCUMENT_ANALYZE,
        label="CAD test",
        payload={"path": str(ifc), "document_id": str(document.id)},
    )
    db_session.commit()
    done = BackgroundJobWorker(db_session).process_once()
    assert done is not None
    assert done.result.get("facts_materialized") is True

    refreshed = DocumentRepository(db_session).get_document(document.id)
    assert refreshed is not None
    assert refreshed.metadata.get("parse_depth") == "ifc_text_semantics"
    assert refreshed.metadata.get("cad_analyze_completed") is True
    facts = {f.key: f for f in FactRepository(db_session).list_by_project(project.id)}
    assert facts["floors"].value == "2"
