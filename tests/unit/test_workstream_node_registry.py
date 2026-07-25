"""Unit tests for workstream node registry and topo compile."""

from __future__ import annotations

from uuid import uuid4

import pytest

from archium.application.orchestration.workstream_node_registry import (
    HANDLER_RESEARCH,
    HANDLER_SKIP,
    HANDLER_STRATEGY_NOTE,
    compile_workstream_node_specs,
    handler_key_for_type,
    topological_workstream_order,
)
from archium.domain.enums import WorkstreamType
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError


def _ws(
    *,
    title: str,
    wtype: WorkstreamType,
    selected: bool = True,
    deps: list | None = None,
) -> Workstream:
    return Workstream(
        project_id=uuid4(),
        mission_id=uuid4(),
        title=title,
        workstream_type=wtype,
        objective=f"objective for {title}",
        selected=selected,
        dependencies=list(deps or []),
    )


def test_handler_key_mapping() -> None:
    assert handler_key_for_type(WorkstreamType.DOCUMENT_REVIEW) == HANDLER_RESEARCH
    assert handler_key_for_type(WorkstreamType.SITE_ANALYSIS) == HANDLER_STRATEGY_NOTE
    assert handler_key_for_type(WorkstreamType.COST_AND_PHASE) == HANDLER_SKIP


def test_compile_selected_only_and_topo_order() -> None:
    a = _ws(title="A", wtype=WorkstreamType.DOCUMENT_REVIEW)
    b = _ws(
        title="B",
        wtype=WorkstreamType.SITE_ANALYSIS,
        deps=[a.id],
    )
    c = _ws(title="C", wtype=WorkstreamType.COST_AND_PHASE, selected=False)
    specs = compile_workstream_node_specs([a, b, c], selected_only=True)
    assert len(specs) == 2
    assert specs[0].workstream_id == a.id
    assert specs[1].workstream_id == b.id
    assert specs[1].handler_key == HANDLER_STRATEGY_NOTE


def test_topo_rejects_cycles() -> None:
    a_id = uuid4()
    b_id = uuid4()
    a = Workstream(
        id=a_id,
        project_id=uuid4(),
        mission_id=uuid4(),
        title="A",
        objective="a",
        selected=True,
        dependencies=[b_id],
    )
    b = Workstream(
        id=b_id,
        project_id=a.project_id,
        mission_id=a.mission_id,
        title="B",
        objective="b",
        selected=True,
        dependencies=[a_id],
    )
    with pytest.raises(WorkflowError):
        topological_workstream_order([a, b])
