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


def test_ui_pages_prefer_application_api_entry() -> None:
    """APP-029/UoW: pages that open their own DB txn should use application_api/unit_of_work."""
    root = Path(__file__).resolve().parents[2] / "archium" / "ui" / "pages"
    package_root = root.parent.parent.parent
    hits: list[str] = []
    pattern = re.compile(
        r"^\s*(?:from|import)\s+archium\.application\.api\.session\b.*api_from_session"
    )
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], (
        "pages should use application_api()/unit_of_work(), not api_from_session:\n"
        + "\n".join(hits)
    )


def test_ui_does_not_import_get_session() -> None:
    """APP-029: UI opens transactions via unit_of_work/application_api only."""
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    package_root = root.parent.parent
    pattern = re.compile(
        r"^\s*(?:from|import)\s+archium\.infrastructure\.database\.session\b"
        r".*\bget_session\b"
    )
    call_pattern = re.compile(r"\bget_session\s*\(")
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
        for match in call_pattern.finditer(text):
            # allow unrelated names like get_session_export_policy / get_session_for_run
            start = match.start()
            line_start = text.rfind("\n", 0, start) + 1
            line = text[line_start : text.find("\n", start)]
            if "get_session_export_policy" in line or "get_session_for_run" in line:
                continue
            if (
                re.search(r"\bget_session\s*\(", line)
                and re.search(r"(?<![A-Za-z0-9_])get_session\s*\(", line)
            ):
                line_no = text.count("\n", 0, start) + 1
                hits.append(
                    f"{path.relative_to(package_root)}:{line_no}: {line.strip()}"
                )
    assert hits == [], "ui must not call get_session():\n" + "\n".join(hits)


def test_ui_does_not_unwrap_sqlalchemy_session() -> None:
    """APP-029: UI must not use api.session / api.uow / uow.session escape hatches.

    Prefer resource APIs (``api.project``, …) or ``with unit_of_work() as uow`` and
    pass ``uow`` as ``SessionLike``. Never commit/execute via unwrapped Session.
    """
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    package_root = root.parent.parent
    unwrap = re.compile(r"\b(?:api\.session|api\.uow|uow\.session)\b")
    raw_ops = re.compile(
        r"\b(?:api|uow)\.session\.(?:commit|rollback|execute|flush)\b"
    )
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in (raw_ops, unwrap):
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                line = text.splitlines()[line_no - 1].strip()
                hits.append(f"{path.relative_to(package_root)}:{line_no}: {line}")
    # de-dupe if both patterns hit the same span
    hits = list(dict.fromkeys(hits))
    assert hits == [], (
        "ui must not unwrap via api.session / api.uow / uow.session "
        "(use resource APIs or pass uow as SessionLike):\n" + "\n".join(hits)
    )


def test_ui_unit_of_work_blocks_bind_session_before_use() -> None:
    """``with unit_of_work() as uow`` bodies must not use bare ``session`` unbound."""
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if not re.search(r"unit_of_work\s*\([^)]*\)\s+as\s+uow\s*:", line):
                i += 1
                continue
            base = len(line) - len(line.lstrip())
            body: list[tuple[int, str]] = []
            j = i + 1
            while j < len(lines):
                bl = lines[j]
                if bl.strip() == "":
                    body.append((j + 1, bl))
                    j += 1
                    continue
                ind = len(bl) - len(bl.lstrip())
                if ind <= base and bl.strip():
                    break
                body.append((j + 1, bl))
                j += 1
            body_text = "\n".join(text for _, text in body)
            assigns = bool(
                re.search(r"(?m)^\s*session\s*=\s*(uow|api\.uow)\b", body_text)
            )
            for line_no, bl in body:
                code = bl.split("#")[0]
                if (
                    re.search(r"(?<![\w.])session(?![\w])", code)
                    and not re.match(r"^\s*session\s*=", code)
                    and not assigns
                ):
                    rel = path.relative_to(package_root)
                    hits.append(f"{rel}:{line_no}: {bl.strip()}")
            i = j
    assert hits == [], (
        "unit_of_work() as uow blocks use bare session without "
        "`session = uow` (or pass uow directly):\n" + "\n".join(hits)
    )
