import { addContentHeader, addNotes } from "../components/header.mjs";
import { addImageOrPlaceholder } from "../core/image-fit.mjs";
import { bulletRuns } from "../core/text-fit.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderThesisSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  if (slide.message) {
    page.addShape(pres.shapes.RECTANGLE, {
      x: theme.spacing.marginX,
      y: 1.4,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 3.8,
      fill: { color: theme.colors.light },
      line: { color: theme.colors.light },
    });
    page.addText(slide.message, {
      x: theme.spacing.marginX + 0.3,
      y: 1.7,
      w: theme.slide_size.width - theme.spacing.marginX * 2 - 0.6,
      h: 3.2,
      fontSize: 22,
      color: theme.colors.text,
      fontFace: theme.fonts.body,
      valign: "mid",
    });
  }
  addNotes(page, slide.speaker_notes);
}

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderSectionSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  page.background = { color: theme.colors.accent };
  page.addText(slide.title, {
    x: theme.spacing.marginX,
    y: 2.2,
    w: theme.slide_size.width - theme.spacing.marginX * 2,
    h: 1.0,
    fontSize: theme.component_styles.section.fontSize,
    bold: true,
    color: theme.colors.onPrimary,
    fontFace: theme.fonts.heading,
    align: "center",
  });
  if (slide.subtitle) {
    page.addText(slide.subtitle, {
      x: theme.spacing.marginX,
      y: 3.3,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 0.8,
      fontSize: 16,
      color: theme.colors.subtitle,
      fontFace: theme.fonts.body,
      align: "center",
    });
  }
  addNotes(page, slide.speaker_notes);
}

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderBulletsSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  if (slide.message) {
    page.addText(slide.message, {
      x: theme.spacing.marginX,
      y: 1.35,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 0.8,
      fontSize: 16,
      bold: true,
      color: theme.colors.text,
      fontFace: theme.fonts.body,
    });
  }
  if ((slide.bullets ?? []).length > 0) {
    page.addText(bulletRuns(slide.bullets), {
      x: theme.spacing.marginX + 0.2,
      y: slide.message ? 2.2 : 1.5,
      w: theme.slide_size.width - theme.spacing.marginX * 2 - 0.2,
      h: 3.8,
      fontSize: 16,
      color: theme.colors.text,
      fontFace: theme.fonts.body,
    });
  }
  addNotes(page, slide.speaker_notes);
}

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderMessageSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  if (slide.message) {
    page.addText(slide.message, {
      x: theme.spacing.marginX,
      y: 1.5,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 3.8,
      fontSize: 20,
      color: theme.colors.text,
      fontFace: theme.fonts.body,
      valign: "top",
    });
  }
  addNotes(page, slide.speaker_notes);
}

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderImageContentSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  const textWidth = (slide.images ?? []).length > 0 ? 4.8 : theme.slide_size.width - theme.spacing.marginX * 2;
  if (slide.message) {
    page.addText(slide.message, {
      x: theme.spacing.marginX,
      y: 1.4,
      w: textWidth,
      h: 0.9,
      fontSize: 16,
      bold: true,
      color: theme.colors.text,
      fontFace: theme.fonts.body,
    });
  }
  if ((slide.bullets ?? []).length > 0) {
    page.addText(bulletRuns(slide.bullets), {
      x: theme.spacing.marginX + 0.2,
      y: slide.message ? 2.3 : 1.5,
      w: textWidth - 0.2,
      h: 3.5,
      fontSize: 15,
      color: theme.colors.text,
      fontFace: theme.fonts.body,
    });
  }
  for (const image of slide.images ?? []) {
    addImageOrPlaceholder(pres, page, image, theme, {
      x: image.x ?? 5.0,
      y: image.y ?? 1.5,
      w: image.w ?? 4.0,
      h: image.h ?? 3.5,
    });
  }
  addNotes(page, slide.speaker_notes);
}

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderImageFullSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  const image = (slide.images ?? [])[0];
  if (image) {
    addImageOrPlaceholder(pres, page, image, theme, {
      x: image.x ?? theme.spacing.marginX,
      y: image.y ?? 1.45,
      w: image.w ?? theme.slide_size.width - theme.spacing.marginX * 2,
      h: image.h ?? 3.85,
    });
  }
  if (slide.message) {
    page.addText(slide.message, {
      x: theme.spacing.marginX,
      y: 5.05,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 0.45,
      fontSize: 13,
      color: theme.colors.muted,
      fontFace: theme.fonts.body,
      align: "center",
    });
  }
  addNotes(page, slide.speaker_notes);
}

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderTimelineSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  const items = slide.timeline_items ?? [];
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
  if (items.length === 0) {
    addNotes(page, slide.speaker_notes);
    return;
  }
  const axisY = slide.message ? 3.05 : 2.75;
  page.addShape("line", {
    x: 0.9,
    y: axisY,
    w: 8.2,
    h: 0,
    line: { color: theme.colors.accent, width: 2 },
  });
  const slotWidth = 8.2 / items.length;
  items.forEach((item, index) => {
    const centerX = 0.9 + slotWidth * index + slotWidth / 2;
    page.addShape("ellipse", {
      x: centerX - 0.12,
      y: axisY - 0.12,
      w: 0.24,
      h: 0.24,
      fill: { color: theme.colors.accent },
      line: { color: theme.colors.accent },
    });
    page.addText(item.label, {
      x: centerX - slotWidth / 2 + 0.05,
      y: axisY - 0.95,
      w: slotWidth - 0.1,
      h: 0.65,
      fontSize: 12,
      bold: true,
      color: theme.colors.primary,
      fontFace: theme.fonts.heading,
      align: "center",
    });
    page.addText(item.text, {
      x: centerX - slotWidth / 2 + 0.05,
      y: axisY + 0.25,
      w: slotWidth - 0.1,
      h: 1.35,
      fontSize: 12,
      color: theme.colors.text,
      fontFace: theme.fonts.body,
      align: "center",
      valign: "top",
    });
  });
  addNotes(page, slide.speaker_notes);
}

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderClosingSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  page.background = { color: theme.colors.primary };
  page.addText(slide.title, {
    x: theme.spacing.marginX,
    y: 2.0,
    w: theme.slide_size.width - theme.spacing.marginX * 2,
    h: 1.0,
    fontSize: 28,
    bold: true,
    color: theme.colors.onPrimary,
    fontFace: theme.fonts.heading,
    align: "center",
  });
  if (slide.message) {
    page.addText(slide.message, {
      x: theme.spacing.marginX,
      y: 3.1,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 1.2,
      fontSize: 18,
      color: theme.colors.subtitle,
      fontFace: theme.fonts.body,
      align: "center",
    });
  }
  addNotes(page, slide.speaker_notes);
}
