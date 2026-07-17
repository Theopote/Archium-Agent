#!/usr/bin/env node
/**
 * Convert Archium PresentationSpec JSON into a native-element PPTX via PptxGenJS.
 *
 * Usage:
 *   node render.mjs --input presentation.spec.json --output presentation.editable.pptx
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import pptxgen from "pptxgenjs";
import { validatePresentationSpec } from "./core/validation.mjs";
import { defineSlideMaster, resolveTheme } from "./core/theme.mjs";
import { renderSlide } from "./layouts/index.mjs";

function parseArgs(argv) {
  const args = { input: null, output: null, theme: null };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--input") {
      args.input = argv[index + 1];
      index += 1;
    } else if (token === "--output") {
      args.output = argv[index + 1];
      index += 1;
    } else if (token === "--theme") {
      args.theme = argv[index + 1];
      index += 1;
    }
  }
  if (!args.input || !args.output) {
    throw new Error("Usage: node render.mjs --input <spec.json> --output <file.pptx> [--theme <name>]");
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const inputPath = resolve(args.input);
  const outputPath = resolve(args.output);
  const raw = JSON.parse(readFileSync(inputPath, "utf8"));
  const spec = validatePresentationSpec(raw);
  const theme = resolveTheme(args.theme ?? spec.theme);

  const pres = new pptxgen();
  pres.author = "Archium";
  pres.company = "Archium";
  pres.subject = spec.title ?? "Archium Presentation";
  pres.title = spec.title ?? "Archium Presentation";
  defineSlideMaster(pres, theme);

  for (const slide of spec.slides ?? []) {
    renderSlide(pres, slide, theme);
  }

  await pres.writeFile({ fileName: outputPath });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
