"""Test script for design system integration."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test if all design system modules can be imported."""
    print("Testing imports...")
    
    try:
        from archium.domain.design_system import create_default_design_system
        print("✓ design_system import successful")
    except Exception as e:
        print(f"✗ design_system import failed: {e}")
        return False
    
    try:
        from archium.domain.presentation_templates import get_template, list_templates
        print("✓ presentation_templates import successful")
    except Exception as e:
        print(f"✗ presentation_templates import failed: {e}")
        return False
    
    try:
        from archium.domain.visual_elements import get_visual_elements_library
        print("✓ visual_elements import successful")
    except Exception as e:
        print(f"✗ visual_elements import failed: {e}")
        return False
    
    try:
        from archium.application.intelligent_layout import LayoutOptimizer
        print("✓ intelligent_layout import successful")
    except Exception as e:
        print(f"✗ intelligent_layout import failed: {e}")
        return False
    
    try:
        from archium.application.design_quality_assessment import DesignQualityAssessor
        print("✓ design_quality_assessment import successful")
    except Exception as e:
        print(f"✗ design_quality_assessment import failed: {e}")
        return False
    
    try:
        from archium.application.design_system_integration import DesignSystemIntegrationService
        print("✓ design_system_integration import successful")
    except Exception as e:
        print(f"✗ design_system_integration import failed: {e}")
        return False
    
    return True

def test_design_system_creation():
    """Test design system creation."""
    print("\nTesting design system creation...")
    
    try:
        from archium.domain.design_system import create_default_design_system
        design_system = create_default_design_system()
        print(f"✓ Design system created successfully")
        print(f"  - Color palette: {len(design_system.color_palette.colors)} colors")
        print(f"  - Typography scale: {len(design_system.typography.scale)} sizes")
        return True
    except Exception as e:
        print(f"✗ Design system creation failed: {e}")
        return False

def test_template_system():
    """Test template system."""
    print("\nTesting template system...")
    
    try:
        from archium.domain.presentation_templates import list_templates, get_template
        templates = list_templates()
        print(f"✓ Template system working")
        print(f"  - Available templates: {len(templates)}")
        for template in templates:
            print(f"    - {template.name} ({template.presentation_type.value})")
        return True
    except Exception as e:
        print(f"✗ Template system failed: {e}")
        return False

def test_visual_elements():
    """Test visual elements library."""
    print("\nTesting visual elements library...")
    
    try:
        from archium.domain.visual_elements import get_visual_elements_library
        library = get_visual_elements_library()
        print(f"✓ Visual elements library working")
        print(f"  - Icons: {len(library.icons)}")
        print(f"  - Chart templates: {len(library.chart_templates)}")
        return True
    except Exception as e:
        print(f"✗ Visual elements library failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("Archium Design System Integration Test")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed")
        return 1
    
    # Test design system
    if not test_design_system_creation():
        print("\n❌ Design system test failed")
        return 1
    
    # Test template system
    if not test_template_system():
        print("\n❌ Template system test failed")
        return 1
    
    # Test visual elements
    if not test_visual_elements():
        print("\n❌ Visual elements test failed")
        return 1
    
    print("\n" + "=" * 50)
    print("✅ All tests passed successfully!")
    print("=" * 50)
    return 0

if __name__ == "__main__":
    sys.exit(main())
