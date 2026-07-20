"""Optional PPTX → per-slide PNG screenshots.

Primary path: LibreOffice + Poppler (pdftoppm).
Windows fallback: Microsoft PowerPoint COM (Slide.Export).

Soft-fail when tools are missing — Visual Critic continues geometry-only.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from archium.logging import get_logger

logger = get_logger(__name__, operation="pptx_screenshot")

_DEFAULT_EXPORT_WIDTH = 1920
_DEFAULT_EXPORT_HEIGHT = 1080


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


def find_powerpoint() -> str | None:
    """Return PowerPoint executable path when available (Windows)."""
    if sys.platform != "win32":
        return None
    candidates = [
        Path(r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE"),
        Path(r"C:\Program Files\Microsoft Office\Office16\POWERPNT.EXE"),
        Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE"),
        Path(r"C:\Program Files (x86)\Microsoft Office\Office16\POWERPNT.EXE"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def libreoffice_screenshot_tools_available() -> bool:
    return find_libreoffice() is not None and find_pdftoppm() is not None


def screenshot_tools_available() -> bool:
    """True when either LibreOffice+pdftoppm or Windows PowerPoint can rasterize PPTX."""
    return libreoffice_screenshot_tools_available() or find_powerpoint() is not None


def export_pptx_slide_pngs(
    pptx_path: Path | str,
    output_dir: Path | str,
    *,
    timeout_seconds: int = 180,
    width: int = _DEFAULT_EXPORT_WIDTH,
    height: int = _DEFAULT_EXPORT_HEIGHT,
) -> list[Path]:
    """Rasterize a PPTX into ``slide_01.png`` … under ``output_dir``.

    Returns an empty list when tools are unavailable or conversion fails.
    Prefer LibreOffice+pdftoppm; fall back to PowerPoint COM on Windows.
    """
    pptx = Path(pptx_path)
    out = Path(output_dir)
    if not pptx.is_file():
        logger.warning("PPTX screenshot skipped: file missing %s", pptx)
        return []

    if libreoffice_screenshot_tools_available():
        results = _export_via_libreoffice(pptx, out, timeout_seconds=timeout_seconds)
        if results:
            return results
        logger.warning("LibreOffice screenshot path failed; trying PowerPoint fallback")

    if find_powerpoint() is not None:
        return _export_via_powerpoint(
            pptx,
            out,
            timeout_seconds=timeout_seconds,
            width=width,
            height=height,
        )

    logger.info(
        "PPTX screenshot skipped: LibreOffice=%s pdftoppm=%s PowerPoint=%s",
        bool(find_libreoffice()),
        bool(find_pdftoppm()),
        bool(find_powerpoint()),
    )
    return []


def _export_via_libreoffice(
    pptx: Path,
    out: Path,
    *,
    timeout_seconds: int,
) -> list[Path]:
    soffice = find_libreoffice()
    pdftoppm = find_pdftoppm()
    if soffice is None or pdftoppm is None:
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


def _export_via_powerpoint(
    pptx: Path,
    out: Path,
    *,
    timeout_seconds: int,
    width: int,
    height: int,
) -> list[Path]:
    """Rasterize slides with PowerPoint COM via PowerShell (no pywin32 required)."""
    out.mkdir(parents=True, exist_ok=True)
    # Clear previous slide_*.png so we can detect fresh exports.
    for stale in out.glob("slide_*.png"):
        stale.unlink(missing_ok=True)

    pptx_literal = str(pptx.resolve()).replace("'", "''")
    out_literal = str(out.resolve()).replace("'", "''")
    script = f"""
$ErrorActionPreference = 'Stop'
$pptxPath = '{pptx_literal}'
$outDir = '{out_literal}'
$width = {int(width)}
$height = {int(height)}
$ppt = New-Object -ComObject PowerPoint.Application
try {{
  # msoTrue = -1; WithWindow=$false keeps export mostly headless.
  $ppt.Visible = -1
  $pres = $ppt.Presentations.Open($pptxPath, $true, $false, $false)
  try {{
    $index = 1
    foreach ($slide in $pres.Slides) {{
      $dest = Join-Path $outDir ('slide_{{0:D2}}.png' -f $index)
      $slide.Export($dest, 'PNG', $width, $height)
      $index++
    }}
  }} finally {{
    $pres.Close()
  }}
}} finally {{
  $ppt.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}}
"""
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            logger.warning(
                "PowerPoint screenshot failed (%s): %s",
                completed.returncode,
                (completed.stderr or completed.stdout or "")[:500],
            )
            return []
        results = sorted(out.glob("slide_*.png"))
        if not results:
            logger.warning("PowerPoint produced no PNGs for %s", pptx.name)
        return results
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("PowerPoint screenshot failed: %s", exc)
        return []
