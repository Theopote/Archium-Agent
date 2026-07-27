"""KN-003 — export facts must use generation eligibility filter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from archium.application.knowledge_isolation import filter_generation_facts
from archium.application.pptxgen_renderer_factory import create_pptxgen_renderer
from archium.config.settings import Settings
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer


def _fact(
    *,
    key: str,
    status: VerificationStatus,
    value: str = "1",
) -> ProjectFact:
    return ProjectFact(
        project_id=uuid4(),
        key=key,
        label=key,
        value=value,
        verification_status=status,
    )


def test_filter_drops_conflicted_and_unconfirmed_critical() -> None:
    confirmed = _fact(key="site_area", status=VerificationStatus.USER_CONFIRMED)
    conflicted = _fact(key="building_area", status=VerificationStatus.CONFLICTED)
    unconfirmed_critical = _fact(key="plot_ratio", status=VerificationStatus.EXTRACTED)
    ok_general = _fact(key="design_theme", status=VerificationStatus.EXTRACTED)

    eligible = filter_generation_facts(
        [confirmed, conflicted, unconfirmed_critical, ok_general]
    )
    keys = {fact.key for fact in eligible}
    assert "site_area" in keys
    assert "design_theme" in keys
    assert "building_area" not in keys
    assert "plot_ratio" not in keys


def test_renderer_uses_injected_fact_resolver_not_raw_repo() -> None:
    project_id = uuid4()
    eligible = [_fact(key="site_area", status=VerificationStatus.USER_CONFIRMED)]
    called: list[UUID] = []

    def resolver(pid: UUID) -> list[ProjectFact]:
        called.append(pid)
        return eligible

    renderer = PptxGenPresentationRenderer(
        Settings(_env_file=None),
        session=MagicMock(),
        fact_resolver=resolver,
    )
    with patch(
        "archium.infrastructure.renderers.pptxgen_renderer.FactRepository"
    ) as repo_cls:
        resolved = renderer._resolve_project_facts(project_id)
        repo_cls.assert_not_called()
    assert called == [project_id]
    assert resolved == eligible


def test_factory_wires_generation_eligible_facts() -> None:
    session = MagicMock()
    project_id = uuid4()
    expected = [_fact(key="site_area", status=VerificationStatus.USER_CONFIRMED)]

    with patch(
        "archium.application.project_knowledge_service.ProjectKnowledgeService"
    ) as svc_cls:
        svc_cls.return_value.generation_eligible_facts.return_value = expected
        renderer = create_pptxgen_renderer(
            Settings(_env_file=None),
            session=session,
        )
        assert renderer._fact_resolver is not None
        got = renderer._resolve_project_facts(project_id)

    svc_cls.assert_called_once_with(session)
    svc_cls.return_value.generation_eligible_facts.assert_called_once_with(project_id)
    assert got == expected


def test_factory_without_session_has_no_fact_resolver() -> None:
    renderer = create_pptxgen_renderer(Settings(_env_file=None), session=None)
    assert renderer._fact_resolver is None
