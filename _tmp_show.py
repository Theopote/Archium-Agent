from pathlib import Path

snippets = {
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\application\visual\slide_preview_service.py"): range(140, 155),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\infrastructure\llm\trace.py"): list(range(125, 140)) + list(range(188, 200)),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\application\process\design_process_pointer.py"): range(120, 150),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\application\orchestration\workflow_orchestration_service.py"): list(range(165, 180)) + list(range(612, 628)),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\ui\rag_preview_panel.py"): range(95, 115),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\ui\pages\template_induction.py"): list(range(150, 165)) + list(range(203, 215)),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\ui\studio\slide_canvas_enhanced.py"): list(range(90, 105)) + list(range(128, 140)),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\ui\planning_service.py"): range(1045, 1058),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\ui\pages\concept_exploration.py"): range(272, 285),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\workflow\planning_nodes.py"): range(198, 215),
    Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\workflow\workstream_execution_graph.py"): range(105, 120),
}
for p, rng in snippets.items():
    lines = p.read_text(encoding="utf-8").splitlines()
    print("====", p.name, "====")
    for i in rng:
        if 1 <= i <= len(lines):
            print(f"{i}:{lines[i-1]}")
