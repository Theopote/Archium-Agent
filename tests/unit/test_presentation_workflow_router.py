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


def _beautify_snapshot(deck: Deck) -> dict[str, object]:
    return {
        "page_count": len(deck.pages),
        "page_order": deck.pages,
        "wording": deck.wording,
        "citations": deck.citations,
    }


def test_router_dispatches_to_the_selected_application_service() -> None:
    calls: list[str] = []
    source = Deck(("a", "b"), ("A", "B"), ("c1",))
    router = PresentationWorkflowRouter(
        {PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: lambda deck: calls.append("beautify") or deck},
        snapshotters={PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: _beautify_snapshot},
    )
    assert router.execute(
        PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK,
        source,
        available_inputs={"source_deck"},
    ) == source
    assert calls == ["beautify"]


def test_beautify_route_fails_closed_when_wording_changes() -> None:
    source = Deck(("a",), ("original",), ("c1",))
    router = PresentationWorkflowRouter(
        {PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: lambda deck: Deck(deck.pages, ("rewritten",), deck.citations)},
        snapshotters={PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: _beautify_snapshot},
    )
    with pytest.raises(WorkflowError, match="changed=\\['wording'\\]"):
        router.execute(
            PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK,
            source,
            available_inputs={"source_deck"},
        )


def test_preserving_route_requires_a_snapshotter_before_handler_runs() -> None:
    called = False
    def handler(deck: Deck) -> Deck:
        nonlocal called
        called = True
        return deck
    router = PresentationWorkflowRouter({PresentationWorkflowRoute.ENHANCE_NATIVE_DECK: handler})
    with pytest.raises(WorkflowError, match="no snapshotter"):
        router.execute(
            PresentationWorkflowRoute.ENHANCE_NATIVE_DECK,
            Deck(("a",), ("A",), ()),
            available_inputs={"source_deck"},
        )
    assert called is False


def test_router_rejects_unregistered_route_without_fallback() -> None:
    router = PresentationWorkflowRouter({})
    with pytest.raises(WorkflowError, match="no executable handler"):
        router.execute(
            PresentationWorkflowRoute.ENHANCE_NATIVE_DECK,
            object(),
            available_inputs={"source_deck"},
        )
