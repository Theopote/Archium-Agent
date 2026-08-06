"""
Tests for FreeformNode compilation in RenderSceneCompiler
"""

import pytest

from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.domain.slide import SlideSpec
from archium.domain.visual.design_system import ColorSystem, DesignSystem, SpacingSystem, TypographySystem
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import FreeformNode


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


class TestFreeformNodeCompilation:
    """Test freeform polygon element compilation."""

    def test_compile_freeform_triangle(self):
        """Test basic triangle compilation."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="triangle",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.FREEFORM,
                    x=100,
                    y=100,
                    width=100,
                    height=100,
                    freeform_points=[
                        (50, 0),    # Top center
                        (100, 100), # Bottom right
                        (0, 100),   # Bottom left
                    ],
                    fill_color="#ff0000",
                    stroke_color="#000000",
                    stroke_width=2.0,
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test freeform triangle",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        # Should have 1 freeform node
        assert len(scene.nodes) == 1

        freeform = scene.nodes[0]
        assert isinstance(freeform, FreeformNode)
        assert len(freeform.points) == 3

        # Points should be converted to absolute coordinates
        assert freeform.points[0].x == 150  # 100 + 50
        assert freeform.points[0].y == 100  # 100 + 0
        assert freeform.points[1].x == 200  # 100 + 100
        assert freeform.points[1].y == 200  # 100 + 100
        assert freeform.points[2].x == 100  # 100 + 0
        assert freeform.points[2].y == 200  # 100 + 100

        assert freeform.fill_color == "#ff0000"
        assert freeform.stroke_color == "#000000"
        assert freeform.stroke_width == 2.0
        assert freeform.closed is True

    def test_compile_freeform_polygon(self):
        """Test pentagon compilation."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="pentagon",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.FREEFORM,
                    x=200,
                    y=150,
                    width=120,
                    height=120,
                    freeform_points=[
                        (60, 0),    # Top
                        (120, 40),  # Top right
                        (100, 120), # Bottom right
                        (20, 120),  # Bottom left
                        (0, 40),    # Top left
                    ],
                    fill_color="#00ff00",
                    stroke_color="#333333",
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test pentagon",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        freeform_nodes = [n for n in scene.nodes if n.node_type == "freeform"]
        assert len(freeform_nodes) == 1

        freeform = freeform_nodes[0]
        assert len(freeform.points) == 5
        assert freeform.fill_color == "#00ff00"

    def test_compile_freeform_open_path(self):
        """Test open path (not closed polygon)."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="path",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.FREEFORM,
                    x=100,
                    y=100,
                    width=200,
                    height=150,
                    freeform_points=[
                        (0, 75),
                        (50, 0),
                        (100, 75),
                        (150, 0),
                        (200, 75),
                    ],
                    freeform_closed=False,  # Open path
                    fill_color=None,  # No fill for open path
                    stroke_color="#0000ff",
                    stroke_width=3.0,
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test open path",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        freeform_nodes = [n for n in scene.nodes if n.node_type == "freeform"]
        assert len(freeform_nodes) == 1

        freeform = freeform_nodes[0]
        assert freeform.closed is False
        assert freeform.fill_color is None
        assert freeform.stroke_color == "#0000ff"
        assert freeform.stroke_width == 3.0

    def test_compile_freeform_stroke_only(self):
        """Test freeform with stroke only (no fill)."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="outline",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.FREEFORM,
                    x=100,
                    y=100,
                    width=100,
                    height=100,
                    freeform_points=[
                        (0, 0),
                        (100, 0),
                        (100, 100),
                        (0, 100),
                    ],
                    fill_color=None,  # No fill
                    stroke_color="#ff00ff",
                    stroke_width=2.5,
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test stroke only",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        freeform_nodes = [n for n in scene.nodes if n.node_type == "freeform"]
        assert len(freeform_nodes) == 1

        freeform = freeform_nodes[0]
        assert freeform.fill_color is None
        assert freeform.stroke_color == "#ff00ff"

    def test_compile_freeform_defaults(self):
        """Test freeform with default stroke from design system."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="default_stroke",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.FREEFORM,
                    x=100,
                    y=100,
                    width=100,
                    height=100,
                    freeform_points=[
                        (0, 0),
                        (100, 0),
                        (50, 100),
                    ],
                    fill_color="#ffff00",
                    # No stroke_color specified - should use design system
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test defaults",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        freeform_nodes = [n for n in scene.nodes if n.node_type == "freeform"]
        assert len(freeform_nodes) == 1

        freeform = freeform_nodes[0]
        # Should use design system border color
        assert freeform.stroke_color is not None
        assert freeform.stroke_width == 1.0  # Default

    def test_compile_freeform_too_few_points(self):
        """Test that freeform with < 3 points is skipped."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="invalid",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.FREEFORM,
                    x=100,
                    y=100,
                    width=100,
                    height=100,
                    freeform_points=[
                        (0, 0),
                        (100, 100),
                    ],  # Only 2 points - invalid
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test too few points",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        # Should have no nodes (freeform skipped)
        freeform_nodes = [n for n in scene.nodes if n.node_type == "freeform"]
        assert len(freeform_nodes) == 0

    def test_compile_freeform_no_points(self):
        """Test that freeform without points is skipped."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                LayoutElement(
                    id="no_points",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.FREEFORM,
                    x=100,
                    y=100,
                    width=100,
                    height=100,
                    freeform_points=None,  # No points
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Test no points",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        # Should have no nodes
        freeform_nodes = [n for n in scene.nodes if n.node_type == "freeform"]
        assert len(freeform_nodes) == 0

    def test_compile_freeform_analysis_zone(self):
        """Test freeform as analysis zone overlay (real-world use case)."""
        layout = LayoutPlan(
            id="test-plan",
            layout_family="analytical_diagram",
            elements=[
                # Base image
                LayoutElement(
                    id="site_image",
                    role=LayoutElementRole.HERO_IMAGE,
                    content_type=LayoutContentType.IMAGE,
                    x=50,
                    y=50,
                    width=860,
                    height=440,
                    content_ref="site_plan.jpg",
                ),
                # Analysis zone overlay
                LayoutElement(
                    id="zone_a",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.FREEFORM,
                    x=100,
                    y=150,
                    width=200,
                    height=150,
                    freeform_points=[
                        (20, 0),
                        (180, 30),
                        (200, 150),
                        (0, 120),
                    ],
                    fill_color="#ff000033",  # Semi-transparent red
                    stroke_color="#ff0000",
                    stroke_width=2.0,
                    z_index=10,  # Above image
                ),
            ],
        )

        slide = SlideSpec(
            id="test-slide",
            slide_number=1,
            content="Site analysis",
        )

        design_system = create_test_design_system()
        compiler = RenderSceneCompiler()

        scene = compiler.compile(
            slide=slide,
            layout_plan=layout,
            design_system=design_system,
        )

        # Should have image + freeform overlay
        freeform_nodes = [n for n in scene.nodes if n.node_type == "freeform"]
        assert len(freeform_nodes) == 1

        zone = freeform_nodes[0]
        assert zone.z_index == 10
        assert zone.fill_color == "#ff000033"  # Semi-transparent
        assert zone.closed is True
