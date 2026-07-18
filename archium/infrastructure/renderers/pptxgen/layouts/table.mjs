import { addContentHeader, addNotes } from "../components/header.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderTableSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);

  const table = slide.table ?? {};
  const headers = table.headers ?? [];
  const rows = table.rows ?? [];

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

  const startY = slide.message ? 2.0 : 1.55;
  const tableWidth = theme.slide_size.width - theme.spacing.marginX * 2;

  if (headers.length > 0 && rows.length > 0) {
    const headerRow = headers.map((header) => ({
      text: header,
      options: {
        bold: true,
        fill: { color: theme.colors.light },
        color: theme.colors.primary,
        fontFace: theme.fonts.heading,
        fontSize: 12,
      },
    }));
    const bodyRows = rows.map((row) =>
      row.map((cell) => ({
        text: cell ?? "",
        options: {
          color: theme.colors.text,
          fontFace: theme.fonts.body,
          fontSize: 12,
        },
      })),
    );
    page.addTable([headerRow, ...bodyRows], {
      x: theme.spacing.marginX,
      y: startY,
      w: tableWidth,
      colW: Array(headers.length).fill(tableWidth / headers.length),
      border: { type: "solid", pt: 0.5, color: theme.colors.muted },
      margin: 0.05,
    });
  } else {
    page.addText("暂无可绘制的表格数据", {
      x: theme.spacing.marginX,
      y: startY + 1.2,
      w: tableWidth,
      h: 0.6,
      fontSize: 14,
      color: theme.colors.muted,
      fontFace: theme.fonts.body,
      align: "center",
    });
  }

  addNotes(page, slide.speaker_notes);
}
