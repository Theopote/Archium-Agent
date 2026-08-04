"""End-to-end integration test for complete presentation workflow.

This test covers the full user journey from project creation to presentation export,
testing the integration of all major components.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.asset_matching_service import AssetMatchingService
from archium.application.export_service import PresentationExportService
from archium.application.ingestion_service import IngestionService
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.config.settings import Settings
from archium.domain.presentation import PresentationBrief
from archium.domain.project import Project


@pytest.mark.integration
def test_complete_presentation_workflow(
    db_session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Test the complete workflow from project creation to presentation export."""
    
    # Step 1: Create a project
    project = Project(
        id=uuid4(),
        name="Test Hospital Renovation",
        description="End-to-end test project",
        organization_id=uuid4(),
    )
    
    # Step 2: Ingest documents
    ingestion_service = IngestionService(db_session, settings=test_settings)
    
    # Create a test document
    test_doc_path = tmp_path / "test_document.txt"
    test_doc_path.write_text("Hospital renovation project with site analysis and design proposals.")
    
    # Ingest the document
    ingestion_result = ingestion_service.ingest_document(
        project_id=project.id,
        file_path=test_doc_path,
        filename="test_document.txt",
    )
    
    assert ingestion_result.success
    assert ingestion_result.document_id is not None
    
    # Step 3: Create presentation brief
    brief = PresentationBrief(
        id=uuid4(),
        project_id=project.id,
        title="Hospital Renovation Presentation",
        target_audience="Hospital Board",
        presentation_type="design_review",
        key_messages=[
            "Site analysis shows opportunities for expansion",
            "Design proposal meets all regulatory requirements",
            "Budget estimates are within approved range",
        ],
        slide_count_target=10,
    )
    
    # Step 4: Run presentation workflow
    workflow_service = PresentationWorkflowService(db_session, settings=test_settings)
    
    workflow_result = workflow_service.run(
        project_id=project.id,
        brief=brief,
    )
    
    assert workflow_result.success
    assert workflow_result.presentation_id is not None
    assert len(workflow_result.slides) > 0
    
    # Step 5: Match assets to slides
    asset_service = AssetMatchingService(db_session, settings=test_settings)
    
    # Create some test assets
    # (In a real test, these would be actual image files)
    matched_slides, match_count = asset_service.match_presentation_slides(
        project_id=project.id,
        presentation_id=workflow_result.presentation_id,
    )
    
    assert len(matched_slides) == len(workflow_result.slides)
    
    # Step 6: Export presentation
    export_service = PresentationExportService(db_session, settings=test_settings)
    
    export_result = export_service.export_presentation(
        presentation_id=workflow_result.presentation_id,
        export_formats=["json", "markdown"],
        output_dir=tmp_path,
    )
    
    assert export_result.success
    assert export_result.json_path is not None
    assert export_result.json_path.exists()
    assert export_result.markdown_path is not None
    assert export_result.markdown_path.exists()
    
    # Verify exported content
    json_content = export_result.json_path.read_text()
    assert "Hospital Renovation" in json_content
    assert workflow_result.presentation_id in json_content
    
    markdown_content = export_result.markdown_path.read_text()
    assert "Hospital Renovation" in markdown_content


@pytest.mark.integration
def test_presentation_workflow_with_review(
    db_session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Test presentation workflow with review and revision cycle."""
    
    project_id = uuid4()
    
    # Create initial brief
    brief = PresentationBrief(
        id=uuid4(),
        project_id=project_id,
        title="Campus Redevelopment",
        target_audience="University Administration",
        presentation_type="strategic_plan",
        key_messages=[
            "Phase 1 focuses on academic buildings",
            "Phase 2 addresses student housing",
            "Sustainability is a core principle",
        ],
        slide_count_target=8,
    )
    
    workflow_service = PresentationWorkflowService(db_session, settings=test_settings)
    
    # Initial workflow run
    initial_result = workflow_service.run(
        project_id=project_id,
        brief=brief,
    )
    
    assert initial_result.success
    assert len(initial_result.slides) > 0
    
    # Simulate review feedback
    _review_comments = [
        "Slide 3 needs more specific data",
        "Add sustainability metrics to slide 5",
        "Clarify timeline in slide 7",
    ]
    
    # Apply revisions (in real workflow, this would be interactive)
    revised_brief = PresentationBrief(
        **brief.model_dump(),
        key_messages=[
            *brief.key_messages,
            "Include specific sustainability metrics",
        ],
    )
    
    # Re-run workflow with revisions
    revised_result = workflow_service.run(
        project_id=project_id,
        brief=revised_brief,
    )
    
    assert revised_result.success
    assert len(revised_result.slides) > 0
    
    # Export final version
    export_service = PresentationExportService(db_session, settings=test_settings)
    export_result = export_service.export_presentation(
        presentation_id=revised_result.presentation_id,
        export_formats=["json"],
        output_dir=tmp_path,
    )
    
    assert export_result.success


@pytest.mark.integration
def test_multi_format_export_workflow(
    db_session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Test presentation export in multiple formats."""
    
    project_id = uuid4()
    brief = PresentationBrief(
        id=uuid4(),
        project_id=project_id,
        title="Multi-format Export Test",
        target_audience="Technical Team",
        presentation_type="technical_review",
        key_messages=["Test message"],
        slide_count_target=5,
    )
    
    workflow_service = PresentationWorkflowService(db_session, settings=test_settings)
    workflow_result = workflow_service.run(project_id=project_id, brief=brief)
    
    assert workflow_result.success
    
    export_service = PresentationExportService(db_session, settings=test_settings)
    
    # Test multiple export formats
    export_result = export_service.export_presentation(
        presentation_id=workflow_result.presentation_id,
        export_formats=["json", "markdown"],
        output_dir=tmp_path,
    )
    
    assert export_result.success
    assert export_result.json_path.exists()
    assert export_result.markdown_path.exists()
    
    # Verify JSON structure
    import json
    with open(export_result.json_path) as f:
        json_data = json.load(f)
    assert "slides" in json_data
    assert len(json_data["slides"]) > 0
    
    # Verify Markdown structure
    markdown_content = export_result.markdown_path.read_text()
    assert "#" in markdown_content  # Markdown headers


@pytest.mark.integration
def test_workflow_error_handling(
    db_session,
    test_settings: Settings,
) -> None:
    """Test error handling in presentation workflow."""
    
    workflow_service = PresentationWorkflowService(db_session, settings=test_settings)
    
    # Test with invalid project ID
    invalid_project_id = uuid4()
    brief = PresentationBrief(
        id=uuid4(),
        project_id=invalid_project_id,
        title="Error Test",
        target_audience="Test",
        presentation_type="test",
        key_messages=["Test"],
        slide_count_target=3,
    )
    
    result = workflow_service.run(project_id=invalid_project_id, brief=brief)
    
    # Should handle gracefully rather than crash
    assert result is not None
    # Either success=False or appropriate error handling
