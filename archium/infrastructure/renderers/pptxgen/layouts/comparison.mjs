import { addContentHeader, addNotes } from "../components/header.mjs";
import { bulletRuns } from "../core/text-fit.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderComparisonSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  if (slide.message) {
    page.addText(slide.message, {
      x: theme.spacing.marginX,
      y: 1.35,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 0.55,
      fontSize: 15,
      color: theme.colors.muted,
      fontFace: theme.fonts.body,
    });
  }
  const columns = slide.columns ?? [];
  const columnWidth = 4.1;
  const startY = slide.message ? 2.05 : 1.55;
  columns.slice(0, 2).forEach((column, index) => {
    const x = theme.spacing.marginX + index * (columnWidth + theme.spacing.gutter);
    page.addShape("rect", {
      x,
      y: startY,
      w: columnWidth,
      h: 3.15,
      fill: { color: theme.colors.light },
      line: { color: index === 0 ? theme.colors.muted : theme.colors.accent, width: 1 },
    });
    page.addText(column.label ?? `方案 ${index + 1}`, {
      x: x + 0.15,
      y: startY + 0.12,
      w: columnWidth - 0.3,
      h: 0.45,
      fontSize: 16,
      bold: true,
      color: theme.colors.primary,
      fontFace: theme.fonts.heading,
    });
    if (column.message) {
      page.addText(column.message, {
        x: x + 0.15,
        y: startY + 0.55,
        w: columnWidth - 0.3,
        h: 0.55,
        fontSize: 13,
        color: theme.colors.text,
        fontFace: theme.fonts.body,
      });
    }
    const bullets = column.bullets ?? [];
    if (bullets.length > 0) {
      page.addText(bulletRuns(bullets), {
        x: x + 0.2,
        y: startY + (column.message ? 1.05 : 0.65),
        w: columnWidth - 0.35,
        h: 1.85,
        fontSize: 14,
        color: theme.colors.text,
        fontFace: theme.fonts.body,
      });
    }
  });
  addNotes(page, slide.speaker_notes);
}
