/** @typedef {import('../core/theme.mjs').PresentationTheme} PresentationTheme */

/** @param {object} page @param {string} text @param {PresentationTheme} theme @param {object} rect */
export function addCaption(page, text, theme, rect) {
  page.addText(text, {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    fontSize: theme.component_styles.caption.fontSize,
    color: theme.colors.muted,
    fontFace: theme.fonts.caption,
    align: "center",
  });
}
