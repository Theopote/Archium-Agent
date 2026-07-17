import { addContentHeader, addNotes } from "../components/header.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderDataSlide(pres, slide, theme) {
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
  const metrics = slide.metrics ?? [];
  const columns = metrics.length <= 2 ? metrics.length || 1 : 3;
  const cardWidth = (theme.slide_size.width - theme.spacing.marginX * 2) / columns - 0.15;
  const startY = slide.message ? 2.05 : 1.55;
  metrics.forEach((metric, index) => {
    const col = index % columns;
    const row = Math.floor(index / columns);
    const x = theme.spacing.marginX + col * (cardWidth + 0.2);
    const y = startY + row * 1.55;
    page.addShape("rect", {
      x,
      y,
      w: cardWidth,
      h: 1.35,
      fill: { color: theme.colors.light },
      line: { color: theme.colors.light },
    });
    page.addText(metric.label, {
      x: x + 0.12,
      y: y + 0.12,
      w: cardWidth - 0.24,
      h: 0.45,
      fontSize: 12,
      color: theme.colors.muted,
      fontFace: theme.fonts.caption,
    });
    page.addText(metric.value, {
      x: x + 0.12,
      y: y + 0.55,
      w: cardWidth - 0.24,
      h: 0.65,
      fontSize: theme.component_styles.metric.fontSize,
      bold: true,
      color: theme.colors.primary,
      fontFace: theme.fonts.heading,
    });
  });
  addNotes(page, slide.speaker_notes);
}
