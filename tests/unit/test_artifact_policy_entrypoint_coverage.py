from pathlib import Path


def test_all_application_render_scene_writes_use_artifact_policy_gateway() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "application"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "artifact_policy_service.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "_scenes.save(" in source:
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"RenderScene writes bypass ArtifactMutationGuard: {offenders}"
