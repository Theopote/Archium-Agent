from dataclasses import dataclass

import pytest
from archium.application.workflow_route_service import PresentationWorkflowRouter
from archium.domain.workflow_route import PresentationWorkflowRoute
from archium.exceptions import WorkflowError


@dataclass(frozen=True)
class Deck:
    pages: tuple[str, ...]
    wording: tuple[str, ...]
    citations: tuple[str, ...]


@dataclass(frozen=True)
class TemplateFill:
    master: str
    layout: str
    placeholder: str
    theme: str
    placeholder_content: str


def _beautify_snapshot(deck: Deck) -> dict[str, object]:
    return {
        "page_count": len(deck.pages),
        "page_order": deck.pages,
        "wording": deck.wording,
        "citations": deck.citations,
    }


def _fill_snapshot(payload: TemplateFill) -> dict[str, object]:
    return {
        "master": payload.master,
        "layout": payload.layout,
        "placeholder": payload.placeholder,
        "theme": payload.theme,
    }


def test_planned_beautify_route_fails_closed_even_with_injected_handler() -> None:
    calls: list[str] = []
    source = Deck(("a", "b"), ("A", "B"), ("c1",))
    router = PresentationWorkflowRouter(
        {
            PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: (
                lambda deck: calls.append("beautify") or deck
            )
        },
        snapshotters={PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: _beautify_snapshot},
    )
    with pytest.raises(WorkflowError, match="planned only"):
        router.execute(
            PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK,
            source,
            available_inputs={"source_deck"},
        )
    assert calls == []


def test_planned_beautify_route_does_not_reach_preservation_checks() -> None:
    source = Deck(("a",), ("original",), ("c1",))
    router = PresentationWorkflowRouter(
        {
            PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: (
                lambda deck: Deck(deck.pages, ("rewritten",), deck.citations)
            )
        },
        snapshotters={PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: _beautify_snapshot},
    )
    with pytest.raises(WorkflowError, match="planned only"):
        router.execute(
            PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK,
            source,
            available_inputs={"source_deck"},
        )


def test_partial_route_dispatches_and_enforces_preservation() -> None:
    calls: list[str] = []
    source = TemplateFill("m", "l", "p", "t", "before")
    router = PresentationWorkflowRouter(
        {
            PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE: (
                lambda payload: calls.append("fill")
                or TemplateFill(
                    payload.master,
                    payload.layout,
                    payload.placeholder,
                    payload.theme,
                    "after",
                )
            )
        },
        snapshotters={PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE: _fill_snapshot},
    )
    result = router.execute(
        PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE,
        source,
        available_inputs={"native_template", "project_knowledge"},
    )
    assert calls == ["fill"]
    assert result.placeholder_content == "after"


def test_partial_route_fails_closed_when_preserved_field_changes() -> None:
    source = TemplateFill("m", "l", "p", "t", "before")
    router = PresentationWorkflowRouter(
        {
            PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE: (
                lambda payload: TemplateFill("changed-master", payload.layout, payload.placeholder, payload.theme, "after")
            )
        },
        snapshotters={PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE: _fill_snapshot},
    )
    with pytest.raises(WorkflowError, match="changed=\\['master'\\]"):
        router.execute(
            PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE,
            source,
            available_inputs={"native_template", "project_knowledge"},
        )


def test_preserving_route_requires_a_snapshotter_before_handler_runs() -> None:
    called = False

    def handler(payload: TemplateFill) -> TemplateFill:
        nonlocal called
        called = True
        return payload

    router = PresentationWorkflowRouter(
        {PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE: handler}
    )
    with pytest.raises(WorkflowError, match="no snapshotter"):
        router.execute(
            PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE,
            TemplateFill("m", "l", "p", "t", "x"),
            available_inputs={"native_template", "project_knowledge"},
        )
    assert called is False


def test_router_rejects_unregistered_route_without_fallback() -> None:
    router = PresentationWorkflowRouter({})
    with pytest.raises(WorkflowError, match="no registered handler|no executable handler"):
        router.execute(
            PresentationWorkflowRoute.RECOVER_IMAGE_DECK,
            object(),
            available_inputs={"image_deck"},
        )


def test_planned_enhance_route_fails_closed() -> None:
    router = PresentationWorkflowRouter(
        {PresentationWorkflowRoute.ENHANCE_NATIVE_DECK: lambda deck: deck}
    )
    with pytest.raises(WorkflowError, match="planned only"):
        router.execute(
            PresentationWorkflowRoute.ENHANCE_NATIVE_DECK,
            Deck(("a",), ("A",), ()),
            available_inputs={"source_deck"},
        )
