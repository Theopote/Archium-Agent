"""Convert editable PPTX to PDF via LibreOffice (soft-fail when unavailable)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from archium.infrastructure.renderers.pptx_screenshot import find_libreoffice
from archium.logging import get_logger

logger = get_logger(__name__, operation="pptx_pdf")


def convert_pptx_to_pdf(
    pptx_path: Path | str,
    output_dir: Path | str,
    *,
    timeout_seconds: int = 120,
) -> Path | None:
    """Convert a PPTX file to PDF under ``output_dir``; return PDF path or None."""
    pptx = Path(pptx_path)
    out = Path(output_dir)
    if not pptx.is_file():
        logger.warning("PPTX→PDF skipped: file missing %s", pptx)
        return None

    soffice = find_libreoffice()
    if soffice is None:
        logger.info("PPTX→PDF skipped: LibreOffice not found")
        return None

    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{pptx.stem}.pdf"
    try:
        with tempfile.TemporaryDirectory(prefix="archium_pdf_") as tmp:
            tmp_dir = Path(tmp)
            convert = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--norestore",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp_dir),
                    str(pptx.resolve()),
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if convert.returncode != 0:
                logger.warning(
                    "LibreOffice PPTX→PDF failed (%s): %s",
                    convert.returncode,
                    (convert.stderr or convert.stdout or "")[:400],
                )
                return None

            pdfs = list(tmp_dir.glob("*.pdf"))
            if not pdfs:
                logger.warning("LibreOffice produced no PDF for %s", pptx.name)
                return None

            shutil.copy2(pdfs[0], target)
            return target
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("PPTX→PDF conversion error: %s", exc)
        return None
