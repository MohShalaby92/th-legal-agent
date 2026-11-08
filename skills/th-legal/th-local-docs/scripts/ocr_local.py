"""Local OCR with Tesseract (Arabic + English). Nothing leaves the PC.

Tesseract is installed by the team installer (winget UB-Mannheim.TesseractOCR) and the Arabic
model is placed in %LOCALAPPDATA%\\TH-Legal\\tessdata. If Tesseract is missing, functions return None.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path




def _tessdata() -> str | None:
    cands = [Path(os.environ.get("LOCALAPPDATA", "")) / "TH-Legal" / "tessdata",
             Path(__file__).resolve().parents[1] / "tessdata"]
    for c in cands:
        if (c / "ara.traineddata").exists():
            return str(c)
    return None


def _lang(td: str) -> str:
    return "ara+eng" if (Path(td) / "eng.traineddata").exists() else "ara"


def find_tesseract() -> str | None:
    exe = shutil.which("tesseract")
    if exe:
        return exe
    for c in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
              Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe"):
        if c.exists():
            return str(c)
    return None


def status() -> str:
    if not find_tesseract():
        return "local OCR not installed"
    if not _tessdata():
        return "local OCR installed but Arabic model missing"
    return "local OCR ready"


def ocr_image_file(path: Path) -> str | None:
    exe, td = find_tesseract(), _tessdata()
    if not exe or not td:
        return None
    try:
        r = subprocess.run([exe, str(path), "stdout", "-l", _lang(td), "--tessdata-dir", td, "--psm", "3"],
                           capture_output=True, timeout=180,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else None
    except Exception:
        return None


def ocr_page(page, dpi: int = 300) -> str | None:
    """OCR one PyMuPDF page."""
    if not find_tesseract() or not _tessdata():
        return None
    with tempfile.TemporaryDirectory(prefix="th-ocr-") as d:
        png = Path(d) / "p.png"
        page.get_pixmap(dpi=dpi).save(str(png))
        return ocr_image_file(png)
