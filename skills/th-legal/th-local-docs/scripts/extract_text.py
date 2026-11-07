"""Extract text from PDF / DOCX / XLSX / TXT locally, with page markers and scan detection.

  python extract_text.py <file> [--max-chars 60000]

Output (stdout): '=== page N ===' blocks. Pages with no text layer are reported as
'[NO TEXT LAYER – scanned page, needs OCR]'. Requires: pymupdf, python-docx, openpyxl
(install once: python -m pip install pymupdf python-docx openpyxl).
Note: stdout is masked by the privacy shield before the model sees it.
"""
import sys
import unicodedata
from pathlib import Path


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def pdf(p: Path):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # older pymupdf

    doc = fitz.open(str(p))
    if doc.needs_pass:
        yield "[PDF IS PASSWORD-PROTECTED – needs unlock]"
        return
    for i, page in enumerate(doc, 1):
        t = page.get_text("text", sort=True).strip()
        yield f"=== page {i} ==="
        if len(t) < 15:
            imgs = len(page.get_images())
            yield f"[NO TEXT LAYER – scanned page, needs OCR] (images on page: {imgs})"
        else:
            yield norm(t)


def docx(p: Path):
    import docx as _docx

    d = _docx.Document(str(p))
    yield "=== body ==="
    for para in d.paragraphs:
        if para.text.strip():
            yield norm(para.text)
    for ti, table in enumerate(d.tables, 1):
        yield f"=== table {ti} ==="
        for row in table.rows:
            yield " | ".join(norm(c.text.strip()) for c in row.cells)
    for si, sec in enumerate(d.sections, 1):
        hdr = " ".join(p.text for p in sec.header.paragraphs if p.text.strip())
        ftr = " ".join(p.text for p in sec.footer.paragraphs if p.text.strip())
        if hdr or ftr:
            yield f"=== section {si} header/footer ===\n{norm(hdr)}\n{norm(ftr)}"


def xlsx(p: Path):
    import openpyxl

    wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
    for ws in wb.worksheets:
        yield f"=== sheet {ws.title} ==="
        for row in ws.iter_rows(values_only=True):
            if any(v is not None for v in row):
                yield " | ".join("" if v is None else norm(str(v)) for v in row)


def main():
    p = Path(sys.argv[1]).expanduser()
    limit = int(sys.argv[sys.argv.index("--max-chars") + 1]) if "--max-chars" in sys.argv else 60000
    ext = p.suffix.lower()
    gen = {".pdf": pdf, ".docx": docx, ".xlsx": xlsx, ".xlsm": xlsx}.get(ext)
    if gen is None:
        lines = [norm(p.read_text(encoding="utf-8", errors="replace"))]
    else:
        lines = list(gen(p))
    out = "\n".join(lines)
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"FILE: {p.name}  ({ext}, {p.stat().st_size // 1024} KB)")
    print(out[:limit])
    if len(out) > limit:
        print(f"\n[TRUNCATED at {limit} chars of {len(out)} — rerun with --max-chars or read by page]")


if __name__ == "__main__":
    main()
