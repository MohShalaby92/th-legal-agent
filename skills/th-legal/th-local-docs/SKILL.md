---
name: th-local-docs
description: "Use when reading PDF/DOCX/XLSX content for review. Local text extraction with page markers, scan detection and OCR routing."
version: 1.1.0
metadata:
  hermes:
    tags: [th-legal, pdf, docx, xlsx, extraction, ocr, arabic]
---

# قراءة المستندات محليًا — Local text extraction

All reading happens on this PC. Never send a document (or a screenshot of it) to the model as an image.

## Extract
```
python ~/AppData/Local/TH-Legal/th.py extract "<file>" [--max-chars 60000] [--ocr auto|force|off] [--dates]
```
Pre-approved; the output is masked by the script itself before printing (independent of the plugin).
Output has `=== page N ===` markers. Never read documents with ad-hoc `python -c` / `cat` / pymupdf
snippets — their output is not masked by the script.
- Scanned pages are OCR'd **locally** (Tesseract, Arabic+English) automatically (`--ocr auto`); OCR text
  is marked `[OCR]`. Use `--ocr force` when a text layer exists but is garbled (reversed/broken letters).
- `--dates`: prints only dates (page, date, هجري/ميلادي, nearby label such as «حررت بتاريخ»). Use it
  whenever the task only needs dates (e.g. settlement creation dates) — less data, fewer misreads.
- Images (`.jpg/.png/.tif`) are OCR'd too.
- `.doc` / `.xls` (old formats): convert first (iLovePDF Word→PDF, or ask the user to save as .docx).
- Google Docs/Sheets: export as .docx/.xlsx (see `th-google-drive`).
- Long files: read page ranges by re-running with a higher `--max-chars`; never summarise pages you did
  not actually read.

## Problems
| Output | Meaning | Action |
|---|---|---|
| `[NO TEXT LAYER … local OCR not installed]` | scanned, OCR missing | ask the user to run TH-Legal-Setup again (installs OCR); otherwise iLovePDF **OCR PDF** inside an approved plan |
| `[OCR]` text with odd words | OCR misreads | mark values «مقروء آليًا — يُرجى التحقق» |
| `[PDF IS PASSWORD-PROTECTED …]` | locked | ask the user; iLovePDF **Unlock PDF** only if they approve |
| `[BLOCKED] privacy shield …` | masker missing | stop; ask the user to run TH-Legal-Setup again |
| `ModuleNotFoundError` | deps missing | ask permission, then `python -m pip install pymupdf python-docx openpyxl` |

## Writing documents
- Never overwrite originals. Write `<name>.revised.docx` next to it in the task `out/` folder.
- Put tokens where personal data goes; produce the real copy with `pii_render`.
- CSV for Excel: write UTF-8 with BOM (`encoding="utf-8-sig"`) so Arabic displays correctly.
