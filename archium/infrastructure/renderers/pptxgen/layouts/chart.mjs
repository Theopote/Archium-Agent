import { addContentHeader, addNotes } from "../components/header.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderChartSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);

  const chart = slide.chart ?? {};
  const series = chart.series ?? [];
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
  const chartHeight = 3.55;
  const chartWidth = theme.slide_size.width - theme.spacing.marginX * 2;

  if (series.length > 0) {
    page.addChart(
      chart.chart_type ?? "bar",
      series.map((item) => ({
        name: item.name ?? "Series",
        labels: item.labels ?? [],
        values: item.values ?? [],
      })),
      {
        x: theme.spacing.marginX,
        y: startY,
        w: chartWidth,
        h: chartHeight,
        showLegend: chart.show_legend ?? true,
        showValue: chart.show_value ?? false,
        showTitle: Boolean(chart.title),
        title: chart.title ?? "",
        chartColors: [theme.colors.primary, theme.colors.accent, theme.colors.muted],
        legendFontFace: theme.fonts.caption,
        catAxisLabelFontFace: theme.fonts.body,
        valAxisLabelFontFace: theme.fonts.body,
      },
    );
  } else {
    page.addText("暂无可绘制的图表数据", {
      x: theme.spacing.marginX,
      y: startY + 1.2,
      w: chartWidth,
      h: 0.6,
      fontSize: 14,
      color: theme.colors.muted,
      fontFace: theme.fonts.body,
      align: "center",
    });
  }

  addNotes(page, slide.speaker_notes);
}
