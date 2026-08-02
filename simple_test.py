import sys
sys.path.insert(0, r'c:\Users\navib\Desktop\development\Archium-Agent')

try:
    from archium.domain.design_system import create_default_design_system
    print("design_system: OK")
except Exception as e:
    print(f"design_system: FAILED - {e}")

try:
    from archium.domain.presentation_templates import list_templates
    print("presentation_templates: OK")
except Exception as e:
    print(f"presentation_templates: FAILED - {e}")

try:
    from archium.domain.visual_elements import get_visual_elements_library
    print("visual_elements: OK")
except Exception as e:
    print(f"visual_elements: FAILED - {e}")

try:
    from archium.application.intelligent_layout import LayoutOptimizer
    print("intelligent_layout: OK")
except Exception as e:
    print(f"intelligent_layout: FAILED - {e}")

try:
    from archium.application.design_quality_assessment import DesignQualityAssessor
    print("design_quality_assessment: OK")
except Exception as e:
    print(f"design_quality_assessment: FAILED - {e}")

try:
    from archium.application.design_system_integration import DesignSystemIntegrationService
    print("design_system_integration: OK")
except Exception as e:
    print(f"design_system_integration: FAILED - {e}")

try:
    from archium.ui.pages.studio import _render_design_system_panel
    print("studio._render_design_system_panel: OK")
except Exception as e:
    print(f"studio._render_design_system_panel: FAILED - {e}")

print("\nAll imports completed")
