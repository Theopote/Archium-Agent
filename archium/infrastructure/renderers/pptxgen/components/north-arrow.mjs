/** @typedef {import('../core/theme.mjs').PresentationTheme} PresentationTheme */

/** @param {object} page @param {PresentationTheme} theme @param {{ x: number, y: number, size?: number }} pos */
export function addNorthArrow(page, theme, pos) {
  const size = pos.size ?? 0.35;
  page.addText("N", {
    x: pos.x,
    y: pos.y,
    w: size,
    h: size,
    fontSize: 12,
    bold: true,
    color: theme.colors.primary,
    fontFace: theme.fonts.caption,
    align: "center",
    valign: "mid",
  });
  page.addShape("line", {
    x: pos.x + size / 2,
    y: pos.y + size,
    w: 0,
    h: size * 0.8,
    line: { color: theme.colors.primary, width: 2 },
  });
}
