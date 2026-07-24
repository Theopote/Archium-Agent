# Studio Browser Interaction Acceptance Checklist (P0-4)


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
Run against a real Streamlit Studio session — unit tests alone are insufficient.

## Preconditions

- Canvas Editor frontend built (`python -m archium.ui.components.canvas_editor.build_frontend`)
- Sample slide with site plan (总平面) + photo + title text
- Node + LibreOffice available if verifying PPTX export geometry

## Scenario

1. Select 总平面图 (click)
2. Resize ~15% with **Shift** (aspect locked)
3. Drag left (pointermove = local preview only; pointerup = one Command)
4. Lock the drawing
5. Replace a photo (double-click or properties)
6. Edit title (double-click canvas text → commitText)
7. Duplicate title (**Ctrl/Cmd+D** or Copy→Paste); confirm offset clone + selection moves to copy
8. Undo thrice (include duplicate)
9. Redo once
10. Export PPTX and compare positions to Studio

## Pass criteria

| Check | Expected |
|-------|----------|
| Drag gesture | Exactly **one** Scene Revision per pointerup |
| Selection | Not lost after commit / rerun |
| Canvas | No Streamlit flash during pointermove |
| Lock | Locked node cannot drag/resize/duplicate |
| Duplicate | New node + LayoutElement; Undo removes both; Redo restores hit-target |
| Undo branch | Does not overwrite sibling history (`parent_revision_id`) |
| PPTX | Exported geometry matches Studio scene |

## Multi-select extras

- Marquee / Shift multi-select → group move one Revision
- Multi-select → Ctrl/Cmd+D duplicates all unlocked in one Revision
- Align / distribute / equal width / height from properties
- Comment Inbox tab: counts + filters; comments show `scene_revision_id` / hash

## Related markers / docs

- `pptx_visual_regression` CI path (PptxGenJS → LibreOffice → baseline)
- `docs/roadmap/visual-quality-and-editing-sprint.md` Sprint 2
