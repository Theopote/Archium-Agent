"""Guard: UI must not import ORM models (use repositories / application services)."""

from __future__ import annotations

import re
from pathlib import Path

_ORM_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+archium\.infrastructure\.database\.models\b"
)
_REPO_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+archium\.infrastructure\.database\."
    r"(?:repositories|mission_repositories|visual_repositories)\b"
)


def test_ui_does_not_import_orm_models() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _ORM_IMPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "ui must not import ORM models:\n" + "\n".join(hits)


def test_ui_pages_do_not_import_repositories() -> None:
    """APP-029: Streamlit pages go through Application API, not repositories."""
    root = Path(__file__).resolve().parents[2] / "archium" / "ui" / "pages"
    package_root = root.parent.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _REPO_IMPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "ui pages must not import repositories:\n" + "\n".join(hits)


def test_ui_does_not_import_repositories() -> None:
    """APP-029: entire UI package goes through Application API facades."""
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _REPO_IMPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "ui must not import repositories:\n" + "\n".join(hits)


def test_ui_pages_prefer_application_api_for_delivery_and_jobs() -> None:
    """APP-029: pages should not construct Delivery/Job progress services directly."""
    banned = re.compile(
        r"^\s*(?:from|import)\s+archium\.application\."
        r"(?:delivery_record_service|job_progress_service)\b"
    )
    root = Path(__file__).resolve().parents[2] / "archium" / "ui" / "pages"
    package_root = root.parent.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in banned.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "ui pages must use Application API for delivery/jobs:\n" + "\n".join(
        hits
    )


def test_ui_does_not_import_export_services() -> None:
    """APP-029: sync export goes through DeliveryApi/RenderApi, not services in UI."""
    banned = re.compile(
        r"^\s*(?:from|import)\s+archium\.application\."
        r"(?:formal_pptx_export_service|export_service)\b"
    )
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in banned.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "ui must use DeliveryApi/RenderApi for export:\n" + "\n".join(hits)
