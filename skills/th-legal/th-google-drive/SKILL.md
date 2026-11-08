---
name: th-google-drive
description: "Use when files must be found, listed, downloaded or uploaded on Google Drive. Privacy-safe bundled helpers over the user's work browser."
version: 1.1.0
metadata:
  hermes:
    tags: [th-legal, google-drive, browser, download, upload]
---

# Google Drive (عبر متصفح العمل)

Drive is used through the member's own work browser («TH Chrome (العمل)», attached automatically).
The user signs in to Google there themselves. Never type credentials; never change sharing settings.
Check sign-in first: `th browser check` → `google_drive: signed-in`.
A shared folder link that opens while signed out is NOT a sign-in (listing will fail).

## Load the helpers (first line of every Drive `browser_exec` call)
```python
import sys, glob, os; sys.path[:0] = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\hermes\skills\th-legal")) + glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\hermes\profiles\*\skills\th-legal")); import th_tools as th
```

## List (full, via Drive's own API — never the web page)
The Drive web page is a virtual list: a folder of 1,772 items shows ~40. **Never count or conclude from
the page.** Use:
```python
items = th.drive_list("<FOLDER_ID>")      # every child, 1000s in seconds
# each: {id, folder, num, kw, ext, size, created, modified}
#   num = leading number of the name (claim number) · kw = document-type keywords in the name
#   NO names are returned (folder names contain creditor names)
claims = th.drive_find_claims("<ROOT_ID>", 1625, 1675)   # {found:{no: folder_id}, duplicates, missing, total_children}
```
- Typical claim layout (Saad liquidation root `1BZ4Axew6Qj8aLQ-VJpXBAqMkE7fuTbCB`): claim folders are
  named `<claimNo>- <creditor>`; the debtor reply is in a subfolder with kw `رد المدين`; files with kw
  `مدمج` are merged packs; `مخالصة`/`تسوية` = settlement.
- Save listings to the task folder with `th.save_json(...)` so they survive interruptions.
- If a folder name has no leading number, `num` is null: report it as «مجلد دون رقم» — don't guess.

## Download (into the task `in/` folder)
```python
n = th.drive_download("<FILE_ID>", r"~/TH-Work/<task>/in/claim-1630_debtor-reply.pdf")
```
- Choose the local name yourself: claim number + document type + extension (from `ext`). Never a
  person's name. The helper saves under a random name first and renames, so real names never appear.
- It waits until the file is complete and returns the size — compare with `size` from the listing.
- Google Docs/Sheets (no `ext`): ask the user, or export via
  `https://docs.google.com/document/d/<ID>/export?format=docx` (`spreadsheets/d/<ID>/export?format=xlsx`).
- Then read it locally: `th extract "<file>"` (masked; OCR for scans).

## Search
Search by non-personal words only (claim number, document type): list the right folder and filter by
`num`/`kw`. If the user needs a name search, ask them to type it in Drive themselves.

## Upload (approval required right before)
Open the target folder, then set the hidden file input:
```python
doc = cdp("DOM.getDocument", depth=-1)
node = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="input[type=file]")
cdp("DOM.setFileInputFiles", nodeId=node["nodeId"], files=[r"C:\...\file.pdf"])
```
Wait for the upload toast to finish, then re-list with `th.drive_list` to confirm. Never overwrite or
delete existing Drive files unless the user explicitly asks and approves that exact action.

## Pitfalls (learned)
- `alt=media` on clients6 is refused ("unsafe for trusted domain") and cross-origin `uc?export=download`
  fails (CORS) — that is why `drive_download` uses a real browser download.
- Large files: Google may show a "can't scan for viruses" page — the helper adds `confirm=t`; if it still
  times out, ask the user to click «Download anyway» in the work browser.
- Chrome freezes background tabs; the helpers bring the Drive tab forward or open a fresh one.
- Never use `use_real_profile`, never copy a Chrome profile, never kill Chrome (the work browser holds
  the logins).
