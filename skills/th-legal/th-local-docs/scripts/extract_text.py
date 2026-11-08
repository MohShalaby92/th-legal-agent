"""Extract text from PDF / DOCX / XLSX / TXT / images locally — output is privacy-masked BEFORE printing.

  python extract_text.py <file> [--max-chars 60000] [--ocr auto|force|off] [--dates]

  --ocr auto   (default) OCR pages that have no usable text layer, if local Tesseract is installed
  --ocr force  OCR every page (use when the text layer is garbled)
  --dates      print ONLY the dates found (page, date, calendar, nearby label) — not the full text.
               Use this whenever the task only needs dates (e.g. settlement creation dates).

Every line printed goes through the privacy masker first (names, IDs, IBANs, phones -> tokens).
If the masker can't be loaded the script refuses to print (fail-closed).
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _thsafe import mask  # noqa: E402  (exits with [BLOCKED] if the shield is missing)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ocr_local  # noqa: E402


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def _poor(t: str) -> bool:
    letters = re.findall(r"[\u0600-\u06FFA-Za-z]", t)
    return len(t.strip()) < 15 or len(letters) < 10


def pdf(p: Path, ocr_mode: str):
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
        if ocr_mode == "force" or (ocr_mode == "auto" and _poor(t)):
            o = ocr_local.ocr_page(page)
            if o is not None:
                yield "[OCR]"
                yield norm(o)
                continue
            if _poor(t):
                yield f"[NO TEXT LAYER – scanned page, needs OCR] (images on page: {len(page.get_images())}; {ocr_local.status()})"
                continue
        yield norm(t)


def image(p: Path, ocr_mode: str):
    yield "=== page 1 ==="
    o = ocr_local.ocr_image_file(p) if ocr_mode != "off" else None
    yield norm(o) if o is not None else f"[IMAGE – needs OCR] ({ocr_local.status()})"


def docx(p: Path, _ocr: str):
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
        hdr = " ".join(x.text for x in sec.header.paragraphs if x.text.strip())
        ftr = " ".join(x.text for x in sec.footer.paragraphs if x.text.strip())
        if hdr or ftr:
            yield f"=== section {si} header/footer ===\n{norm(hdr)}\n{norm(ftr)}"


def xlsx(p: Path, _ocr: str):
    import openpyxl
    wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
    for ws in wb.worksheets:
        yield f"=== sheet {ws.title} ==="
        for row in ws.iter_rows(values_only=True):
            if any(v is not None for v in row):
                yield " | ".join("" if v is None else norm(str(v)) for v in row)


_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
DATE_RX = re.compile(r"(?<!\d)(\d{1,4})\s*[/\-.\\]\s*(\d{1,2})\s*[/\-.\\]\s*(\d{1,4})(?!\d)\s*(هـ|ه|م)?")
LABEL_RX = re.compile(r"(تاريخ[^\n:]{0,20}|حرر[^\n]{0,10}|بتاريخ|الموافق|Date[^\n:]{0,10})", re.I)


def dates_only(lines):
    page = "?"
    for line in lines:
        m = re.match(r"=== page (\d+) ===", line)
        if m:
            page = m.group(1)
            continue
        flat = line.translate(_DIG)
        for dm in DATE_RX.finditer(flat):
            a, b, c, suf = dm.groups()
            y = a if len(a) == 4 else (c if len(c) == 4 else None)
            if not y:
                continue
            ctx = flat[max(0, dm.start() - 40):dm.start()]
            lab = LABEL_RX.findall(ctx)
            kind = "hijri" if (suf in ("هـ", "ه") or int(y) < 1600) else "gregorian"
            yield f"page {page}: {dm.group(0).strip()}  [{kind}]  label={lab[-1].strip() if lab else '-'}"


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    p = Path(args[0]).expanduser()
    limit = int(args[args.index("--max-chars") + 1]) if "--max-chars" in args else 60000
    ocr_mode = args[args.index("--ocr") + 1] if "--ocr" in args else "auto"
    ext = p.suffix.lower()
    gen = {".pdf": pdf, ".docx": docx, ".xlsx": xlsx, ".xlsm": xlsx,
           ".png": image, ".jpg": image, ".jpeg": image, ".tif": image, ".tiff": image}.get(ext)
    lines = [norm(p.read_text(encoding="utf-8", errors="replace"))] if gen is None else list(gen(p, ocr_mode))
    sys.stdout.reconfigure(encoding="utf-8")
    print(mask(f"FILE: {p.name}  ({ext}, {p.stat().st_size // 1024} KB)"))
    if "--dates" in args:
        for l in lines:
            if l.startswith("["):
                print(mask(l))
        found = list(dates_only(lines))
        print("\n".join(found) if found else "NO DATES FOUND")
        return
    out = "\n".join(lines)
    print(mask(out[:limit]))
    if len(out) > limit:
        print(f"\n[TRUNCATED at {limit} chars of {len(out)} — rerun with --max-chars or read by page]")


if __name__ == "__main__":
    main()
