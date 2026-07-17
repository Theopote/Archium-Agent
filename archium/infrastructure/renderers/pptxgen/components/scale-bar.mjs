/** @typedef {import('../core/theme.mjs').PresentationTheme} PresentationTheme */

/** @param {object} page @param {PresentationTheme} theme @param {{ x: number, y: number, w: number, label?: string }} bar */
export function addScaleBar(page, theme, bar) {
  page.addShape("line", {
    x: bar.x,
    y: bar.y,
    w: bar.w,
    h: 0,
    line: { color: theme.colors.text, width: 2 },
  });
  page.addText(bar.label ?? "比例尺", {
    x: bar.x,
    y: bar.y + 0.08,
    w: bar.w,
    h: 0.2,
    fontSize: theme.component_styles.caption.fontSize,
    color: theme.colors.muted,
    fontFace: theme.fonts.caption,
    align: "center",
  });
}
