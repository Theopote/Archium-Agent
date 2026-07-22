# Narrative mode and artifact ownership

## Narrative mode

`ArchitecturalNarrativeMode` is a mission-level choice independent from visual
`ArtDirection`. A technical-blueprint visual style, for example, can be combined
with a decision-first, evidence-argument, or phased-implementation narrative.

Each registered mode declares its expected `NarrativeStage` sequence, suitable
decision contexts, and any questions that the storyline must answer. The mode is
stored on `ProjectMission`; downstream storyline planning should preserve it
unless a user explicitly changes the mission.

Supported modes:

- decision first
- problem / solution
- evidence / argument
- design process
- option comparison
- technical briefing
- phased implementation
- public storytelling

## Artifact ownership

The ownership registry distinguishes five authorities: source, authored state,
derived artifact, delivery artifact, and validation artifact.

`ProjectKnowledge` is source authority. `OutlinePlan`, `SlideDesignBrief`,
`LayoutPlan`, and `RenderScene` are authored state. Preview images are derived;
PPTX is a delivery artifact; round-trip images and the export manifest are
validation artifacts.

PowerPoint edits do not silently overwrite canonical state. Because PPTX is
editable outside Archium, importing those changes requires an explicit
Import/Reconcile workflow that establishes provenance and resolves conflicts.
