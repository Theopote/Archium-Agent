import { addNotes } from "../components/header.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderTitleSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  page.background = { color: theme.colors.primary };
  page.addText(slide.title, {
    x: theme.spacing.marginX,
    y: 1.8,
    w: theme.slide_size.width - theme.spacing.marginX * 2,
    h: 1.2,
    fontSize: theme.component_styles.title.fontSize,
    bold: true,
    color: theme.colors.onPrimary,
    fontFace: theme.fonts.heading,
  });
  if (slide.subtitle) {
    page.addText(slide.subtitle, {
      x: theme.spacing.marginX,
      y: 3.1,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 0.6,
      fontSize: 18,
      color: theme.colors.subtitle,
      fontFace: theme.fonts.body,
    });
  }
  if (slide.message) {
    page.addText(slide.message, {
      x: theme.spacing.marginX,
      y: 4.0,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 1.0,
      fontSize: 16,
      color: theme.colors.subtitle,
      fontFace: theme.fonts.body,
    });
  }
  addNotes(page, slide.speaker_notes);
}
