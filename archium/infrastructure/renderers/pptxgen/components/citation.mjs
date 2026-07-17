/** @typedef {import('../core/theme.mjs').PresentationTheme} PresentationTheme */

/** @param {object} page @param {string[]} lines @param {PresentationTheme} theme @param {object} rect */
export function addCitationBlock(page, lines, theme, rect) {
  if (!lines.length) {
    return;
  }
  const text = lines.map((line) => `• ${line}`).join("\n");
  page.addText(text, {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    fontSize: theme.component_styles.caption.fontSize,
    color: theme.colors.muted,
    fontFace: theme.fonts.caption,
    valign: "top",
  });
}
