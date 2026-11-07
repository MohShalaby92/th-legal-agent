---
name: th-ilovepdf
description: "Use when a PDF must be merged, split, compressed, converted, OCR'd, edited, rotated, numbered, redacted or unlocked. iLovePDF website workflow via the browser."
version: 1.0.0
metadata:
  hermes:
    tags: [th-legal, pdf, ilovepdf, merge, ocr, convert]
---

# iLovePDF (https://www.ilovepdf.com)

Team policy: PDF operations are done on the iLovePDF website. Files leave the PC during processing, so:
- Upload ONLY files in the approved plan; show the list (count + file names as tokens) and get approval
  right before the first upload of a batch.
- After downloading the result, use the "delete" (trash) option on the download page if present.
- If a file must not be uploaded (the user says so), stop and tell them.

## Tool URLs
| Task | URL |
|---|---|
| دمج Merge | `/merge_pdf` |
| تقسيم Split | `/split_pdf` |
| ضغط Compress | `/compress_pdf` |
| PDF → Word | `/pdf_to_word` |
| Word → PDF | `/word_to_pdf` |
| PDF → Excel / Excel → PDF | `/pdf_to_excel` · `/excel_to_pdf` |
| JPG → PDF / PDF → JPG | `/jpg_to_pdf` · `/pdf_to_jpg` |
| تعديل Edit | `/edit-pdf` |
| OCR | `/ocr-pdf` (choose Arabic + English) |
| تدوير Rotate | `/rotate_pdf` |
| ترقيم الصفحات Page numbers | `/add_pdf_page_number` |
| ترتيب/حذف صفحات Organize | `/organize-pdf` |
| علامة مائية Watermark | `/pdf_add_watermark` |
| فك القفل Unlock / حماية Protect | `/unlock_pdf` · `/protect-pdf` |
| إخفاء Redact | `/redact-pdf` |
| مقارنة Compare | `/compare-pdf` |
| PDF/A · Repair · Crop | `/convert-pdf-to-pdfa` · `/repair-pdf` · `/crop-pdf` |
All under `https://www.ilovepdf.com`. Arabic UI: prefix `/ar` (e.g. `/ar/merge_pdf`) — DOM text differs, so
prefer selectors over button text.

## Generic flow (browser_exec) — verified on merge_pdf
1. `goto_url("https://www.ilovepdf.com/merge_pdf"); wait_for_load()`
2. (Optional) browser download folder: `cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath=r"<task>\\out")`
3. Upload — every tool page has ONE hidden `input[type=file]` (accept=.pdf for PDF tools, multiple):
```python
doc = cdp("DOM.getDocument", depth=-1)
node = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="input[type=file]")
cdp("DOM.setFileInputFiles", nodeId=node["nodeId"], files=[r"...\\a.pdf", r"...\\b.pdf"])
```
4. Wait until all files are listed and the action button exists: poll
   `document.querySelectorAll('.file').length == N && !!document.querySelector('#processTask')`.
   Arrange order if needed (merge: order = upload order; verify against the plan), set options
   (OCR language, compression level…).
5. Click `#processTask` and wait for the result page (`location.href` contains `/download/`).
6. Download: `#pickfiles` on the result page is a direct link (`https://apiNN.ilovepdf.com/v1/download/…`).
   Save it with Python (no cookies needed):
```python
import urllib.request
href = js("document.querySelector('#pickfiles').href")
open(dest, "wb").write(urllib.request.urlopen(urllib.request.Request(href, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read())
```
7. Delete from iLovePDF immediately (verified flow): `#delete` → modal → `#btnDelete`. The page then says
   "This task has already been deleted." (Otherwise files auto-delete after ~2 hours — still delete.)
```python
js("document.querySelector('#delete').click()"); time.sleep(2); js("document.querySelector('#btnDelete').click()")
```
8. Re-check the result locally (`th-local-docs`): page count, order, text present (after OCR), size.

## Notes
- Merge naming convention seen on the platform: `<claimNo> مدمج.pdf` — ask the user for their naming rule.
- Free tier limits (file size / tasks per hour) may block large batches → report clearly, don't loop.
- If the site asks to log in for a feature, ask the user to log in themselves (their own account).
- Edit PDF changes typed in by you come from tokens → they are restored locally to real values before
  typing (privacy shield), so text you insert appears correctly.
