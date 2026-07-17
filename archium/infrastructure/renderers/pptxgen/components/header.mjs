/** @typedef {import('../core/theme.mjs').PresentationTheme} PresentationTheme */

/** @param {import('pptxgenjs').default} pres @param {object} page @param {string} title @param {PresentationTheme} theme */
export function addContentHeader(pres, page, title, theme) {
  page.addText(title, {
    x: theme.spacing.marginX,
    y: theme.spacing.marginY,
    w: theme.slide_size.width - theme.spacing.marginX * 2,
    h: theme.spacing.headerHeight,
    fontSize: theme.component_styles.header.fontSize,
    bold: true,
    color: theme.colors.primary,
    fontFace: theme.fonts.heading,
  });
  page.addShape("rect", {
    x: theme.spacing.marginX,
    y: theme.spacing.marginY + theme.spacing.headerHeight + 0.05,
    w: 1.2,
    h: 0.06,
    fill: { color: theme.colors.accent },
    line: { color: theme.colors.accent },
  });
}

/** @param {object} page @param {PresentationTheme} theme */
export function addFooter(page, theme) {
  if (!theme.footer.enabled || !theme.footer.text) {
    return;
  }
  page.addText(theme.footer.text, {
    x: theme.footer.x,
    y: theme.footer.y,
    w: theme.footer.w,
    h: theme.footer.h,
    fontSize: theme.footer.fontSize,
    color: theme.colors.muted,
    fontFace: theme.fonts.caption,
  });
}

/** @param {object} page @param {string | null | undefined} notes */
export function addNotes(page, notes) {
  if (notes) {
    page.addNotes(notes);
  }
}
