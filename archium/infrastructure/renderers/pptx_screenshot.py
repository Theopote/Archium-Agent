"""Optional PPTX → per-slide PNG screenshots via LibreOffice + Poppler.

Soft-fail when tools are missing — Visual Critic continues geometry-only.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from archium.logging import get_logger

logger = get_logger(__name__, operation="pptx_screenshot")


def find_libreoffice() -> str | None:
    for name in ("soffice", "libreoffice", "soffice.exe"):
        found = shutil.which(name)
        if found:
            return found
    # Common Windows install path.
    candidates = [
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def find_pdftoppm() -> str | None:
    return shutil.which("pdftoppm") or shutil.which("pdftoppm.exe")


def screenshot_tools_available() -> bool:
    return find_libreoffice() is not None and find_pdftoppm() is not None


def export_pptx_slide_pngs(
    pptx_path: Path | str,
    output_dir: Path | str,
    *,
    timeout_seconds: int = 120,
) -> list[Path]:
    """Rasterize a PPTX into ``slide_01.png`` … under ``output_dir``.

    Returns an empty list when tools are unavailable or conversion fails.
    """
    pptx = Path(pptx_path)
    out = Path(output_dir)
    if not pptx.is_file():
        logger.warning("PPTX screenshot skipped: file missing %s", pptx)
        return []

    soffice = find_libreoffice()
    pdftoppm = find_pdftoppm()
    if soffice is None or pdftoppm is None:
        logger.info(
            "PPTX screenshot skipped: LibreOffice=%s pdftoppm=%s",
            bool(soffice),
            bool(pdftoppm),
        )
        return []

    out.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="archium_pptx_") as tmp:
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
                return []

            pdfs = list(tmp_dir.glob("*.pdf"))
            if not pdfs:
                logger.warning("LibreOffice produced no PDF for %s", pptx.name)
                return []

            prefix = tmp_dir / "slide"
            raster = subprocess.run(
                [
                    pdftoppm,
                    "-png",
                    "-r",
                    "144",
                    str(pdfs[0]),
                    str(prefix),
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if raster.returncode != 0:
                logger.warning(
                    "pdftoppm failed (%s): %s",
                    raster.returncode,
                    (raster.stderr or raster.stdout or "")[:400],
                )
                return []

            generated = sorted(tmp_dir.glob("slide*.png"))
            results: list[Path] = []
            for index, source in enumerate(generated, start=1):
                dest = out / f"slide_{index:02d}.png"
                dest.write_bytes(source.read_bytes())
                results.append(dest)
            return results
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("PPTX screenshot failed: %s", exc)
        return []
