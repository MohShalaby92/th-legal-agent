---
name: th-google-drive
description: "Use when files must be found, downloaded or uploaded on Google Drive. Browser-only Drive workflow (no API), privacy-safe."
version: 1.0.0
metadata:
  hermes:
    tags: [th-legal, google-drive, browser, download, upload]
---

# Google Drive (عبر المتصفح فقط)

Team members use Drive only in the browser. The user signs in to Google themselves in the agent's
browser window. Never type Google credentials; never change sharing settings.

## Find
- Folder: open the link the user gives (`https://drive.google.com/drive/folders/<FOLDER_ID>`).
- Search: `https://drive.google.com/drive/search?q=<words>` (use non-personal words: case number,
  document type — NOT a client's name; if the user needs a name search, ask them to type it in the
  Drive search box themselves).
- List items safely (names are masked by the shield; Drive file IDs are in `data-id`):
```python
print(js("""[...document.querySelectorAll('[data-id]')].map(e => {
  const n = (e.innerText || '').split('\\n')[0].trim(); return n ? `${e.getAttribute('data-id')} | ${n}` : null;
}).filter(Boolean).join('\\n')"""))
```
  Drive lazy-loads long folders: scroll the list container and re-read until the count stops growing.
  Switch to list view if grid view hides names.

## Download (into the task `in/` folder)
- Native files (PDF, DOCX, images): `https://drive.google.com/uc?export=download&id=<ID>` fetched with
  the signed-in session (same fetch→base64 pattern as `th-platform`). Large files may return a
  "can't scan for viruses" page — then click its "Download anyway" link in the browser.
- Google Docs → `https://docs.google.com/document/d/<ID>/export?format=docx`
- Google Sheets → `https://docs.google.com/spreadsheets/d/<ID>/export?format=xlsx`
- Alternative: set the browser download folder, then use Drive's own Download menu:
  `cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath=r"C:\\Users\\<u>\\TH-Work\\<task>\\in")`
- Verify each file exists locally and is non-empty; record failures in the ledger.

## Upload (approval required right before)
Open the target folder, then New → File upload, or set the hidden file input directly:
```python
doc = cdp("DOM.getDocument", depth=-1)
node = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="input[type=file]")
cdp("DOM.setFileInputFiles", nodeId=node["nodeId"], files=[r"C:\\...\\file.pdf"])
```
Wait for the upload toast to finish, then re-list the folder to confirm. Never overwrite or delete
existing Drive files unless the user explicitly asks and approves that exact action.
