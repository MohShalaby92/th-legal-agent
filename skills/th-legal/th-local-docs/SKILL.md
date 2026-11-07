---
name: th-local-docs
description: "Use when reading PDF/DOCX/XLSX content for review. Local text extraction with page markers, scan detection and OCR routing."
version: 1.0.0
metadata:
  hermes:
    tags: [th-legal, pdf, docx, xlsx, extraction, ocr, arabic]
---

# قراءة المستندات محليًا — Local text extraction

All reading happens on this PC. Never send a document (or a screenshot of it) to the model as an image.

## Extract
```
python "<skill_dir>/scripts/extract_text.py" "<file>" [--max-chars 60000]
```
(`<skill_dir>` = the path `skill_view` shows for this skill.) Output has `=== page N ===` markers;
personal data is already tokenised by the privacy shield before you see it.
- `.doc` / `.xls` (old formats): convert first (iLovePDF Word→PDF, or ask the user to save as .docx).
- Google Docs/Sheets: export as .docx/.xlsx (see `th-google-drive`).
- Long files: read page ranges by re-running with a higher `--max-chars` or splitting; never summarise
  pages you did not actually read.

## Problems
| Output | Meaning | Action |
|---|---|---|
| `[NO TEXT LAYER – scanned page …]` | scanned image | OCR needed: iLovePDF **OCR PDF** (`th-ilovepdf`, inside an approved plan), then extract again |
| `[PDF IS PASSWORD-PROTECTED …]` | locked | ask the user; iLovePDF **Unlock PDF** only if they approve |
| Arabic letters reversed / broken | bad PDF text layer | try OCR PDF; report "جودة النص ضعيفة" if still bad |
| `ModuleNotFoundError` | deps missing | ask permission, then `hermes plugins enable th-privacy-shield` (installs pymupdf, python-docx, openpyxl) or `python -m pip install pymupdf python-docx openpyxl` |

## Writing documents
- Never overwrite originals. Write `<name>.revised.docx` next to it in the task `out/` folder.
- Put tokens where personal data goes; produce the real copy with `pii_render`.
- CSV for Excel: write UTF-8 with BOM (`encoding="utf-8-sig"`) so Arabic displays correctly.
