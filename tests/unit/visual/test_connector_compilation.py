"""
Tests for ConnectorNode compilation in RenderSceneCompiler
"""

import pytest

from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.domain.slide import SlideSpec
from archium.domain.visual.design_system import ColorSystem, DesignSystem, SpacingSystem, TypographySystem
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.layout import Bounds, LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import ConnectorNode


def create_test_design_system() -> DesignSystem:
    """Create a minimal test design system."""
    return DesignSystem(
        id="test-design",
        colors=ColorSystem(
            primary="#1a1a1a",
            secondary="#666666",
            background="#ffffff",
            text="#000000",
            accent="#0066cc",
        ),
        typography=TypographySystem(
            base_font="Arial",
            heading_font="Arial",
            base_size=12.0,
        ),
        spacing=SpacingSystem(
            base_unit=8.0,
        ),
    )


class TestConnectorNodeCompilation:
    """Test connector element compilation."""

    def test_compile_connector_basic(self):
        """Test basic connector compilation."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="node1",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=100,
                    y=100,
                    width=100,
                    height=80,
                    shape_kind="rectangle",
                ),
                LayoutElement(
                    id="node2",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=300,
                    y=200,
                    width=100,
                    height=80,
                    shape_kind="rectangle",
                ),
                LayoutElement(
                    id="connector1",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.CONNECTOR,
                    x=200,
                    y=140,
                    width=100,
                    height=60,
                    connector_start_node_id="node1",
                    connector_end_node_id="node2",
                    connector_start_anchor="right",
                    connector_end_anchor="left",
                    connector_routing="straight",
                    stroke_color="#333333",
                    stroke_width=2.0,
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test connector",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        # Should have 2 shapes + 1 connector
        assert len(scene.nodes) == 3

        # Find connector node
        connector_nodes = [n for n in scene.nodes if n.node_type == "connector"]
        assert len(connector_nodes) == 1

        connector = connector_nodes[0]
        assert isinstance(connector, ConnectorNode)
        assert connector.start.node_id == "node1"
        assert connector.end.node_id == "node2"
        assert connector.start.anchor == "right"
        assert connector.end.anchor == "left"
        assert connector.routing == "straight"
        assert connector.stroke_color == "#333333"
        assert connector.stroke_width == 2.0

    def test_compile_connector_defaults(self):
        """Test connector compilation with default values."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="node1",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=100,
                    y=100,
                    width=100,
                    height=80,
                ),
                LayoutElement(
                    id="node2",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=300,
                    y=200,
                    width=100,
                    height=80,
                ),
                LayoutElement(
                    id="connector1",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.CONNECTOR,
                    x=200,
                    y=140,
                    width=100,
                    height=60,
                    connector_start_node_id="node1",
                    connector_end_node_id="node2",
                    # No anchor/routing specified - should use defaults
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test connector defaults",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        connector_nodes = [n for n in scene.nodes if n.node_type == "connector"]
        assert len(connector_nodes) == 1

        connector = connector_nodes[0]
        assert connector.start.anchor == "center"  # default
        assert connector.end.anchor == "center"  # default
        assert connector.routing == "straight"  # default
        assert connector.stroke_width == 1.5  # default

    def test_compile_connector_with_label(self):
        """Test connector with label text."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="node1",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=100,
                    y=100,
                    width=100,
                    height=80,
                ),
                LayoutElement(
                    id="node2",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=300,
                    y=200,
                    width=100,
                    height=80,
                ),
                LayoutElement(
                    id="connector1",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.CONNECTOR,
                    x=200,
                    y=140,
                    width=100,
                    height=60,
                    connector_start_node_id="node1",
                    connector_end_node_id="node2",
                    connector_label="Flow",
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test connector label",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        connector_nodes = [n for n in scene.nodes if n.node_type == "connector"]
        assert len(connector_nodes) == 1

        connector = connector_nodes[0]
        assert connector.label == "Flow"

    def test_compile_connector_missing_endpoints(self):
        """Test that connector without endpoints is skipped."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="connector1",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.CONNECTOR,
                    x=200,
                    y=140,
                    width=100,
                    height=60,
                    # Missing connector_start_node_id and connector_end_node_id
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test missing endpoints",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        # Should have no nodes (connector skipped)
        connector_nodes = [n for n in scene.nodes if n.node_type == "connector"]
        assert len(connector_nodes) == 0

    def test_compile_connector_elbow_routing(self):
        """Test connector with elbow routing."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="node1",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=100,
                    y=100,
                    width=100,
                    height=80,
                ),
                LayoutElement(
                    id="node2",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=300,
                    y=300,
                    width=100,
                    height=80,
                ),
                LayoutElement(
                    id="connector1",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.CONNECTOR,
                    x=150,
                    y=180,
                    width=200,
                    height=120,
                    connector_start_node_id="node1",
                    connector_end_node_id="node2",
                    connector_routing="elbow",
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test elbow routing",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        connector_nodes = [n for n in scene.nodes if n.node_type == "connector"]
        assert len(connector_nodes) == 1

        connector = connector_nodes[0]
        assert connector.routing == "elbow"

    def test_compile_connector_invalid_anchor_fallback(self):
        """Test that invalid anchor values fall back to 'center'."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="node1",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=100,
                    y=100,
                    width=100,
                    height=80,
                ),
                LayoutElement(
                    id="node2",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.SHAPE,
                    x=300,
                    y=200,
                    width=100,
                    height=80,
                ),
                LayoutElement(
                    id="connector1",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.CONNECTOR,
                    x=200,
                    y=140,
                    width=100,
                    height=60,
                    connector_start_node_id="node1",
                    connector_end_node_id="node2",
                    connector_start_anchor="invalid_anchor",
                    connector_end_anchor="another_invalid",
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test invalid anchors",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        connector_nodes = [n for n in scene.nodes if n.node_type == "connector"]
        assert len(connector_nodes) == 1

        connector = connector_nodes[0]
        # Should fall back to center
        assert connector.start.anchor == "center"
        assert connector.end.anchor == "center"
