/** @typedef {import('../core/theme.mjs').PresentationTheme} PresentationTheme */

/** @param {object} page @param {Array<{ label: string, color?: string }>} items @param {PresentationTheme} theme @param {object} rect */
export function addLegend(page, items, theme, rect) {
  if (!items.length) {
    return;
  }
  items.forEach((item, index) => {
    const y = rect.y + index * 0.28;
    page.addShape("rect", {
      x: rect.x,
      y,
      w: 0.18,
      h: 0.18,
      fill: { color: item.color ?? theme.colors.accent },
      line: { color: item.color ?? theme.colors.accent },
    });
    page.addText(item.label, {
      x: rect.x + 0.25,
      y: y - 0.02,
      w: rect.w - 0.25,
      h: 0.22,
      fontSize: theme.component_styles.caption.fontSize,
      color: theme.colors.text,
      fontFace: theme.fonts.caption,
    });
  });
}
