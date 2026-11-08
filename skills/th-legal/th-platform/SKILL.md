---
name: th-platform
description: "Use when working on manage.th-lawfirm.sa (cases, claims, attachments, checklists). Map of pages, safe page reading, file download/upload."
version: 1.1.0
metadata:
  hermes:
    tags: [th-legal, platform, livewire, claims, bankruptcy, arabic]
---

# منصة التميمي والحمودي — manage.th-lawfirm.sa

Laravel **Livewire + Flux UI** app, Arabic RTL. Content renders after navigation: wait 2–4 s (or poll for
an element) before reading. Actions are `wire:click` handlers, not links. Default is **read-only**:
editing, uploading, status changes, or saving on the platform need explicit approval just before the click.

## Login
The user logs in themselves (email+password or "تسجيل الدخول باستخدام جوجل") in the work browser
«TH Chrome (العمل)» that the agent is attached to. Never type credentials. Check with
`th browser check` (`platform: signed-in`). The platform session expires
after some time; if any helper says `platform sign-in needed` or you land on `/login`, stop, ask the user
to log in again in that window, then continue from the ledger.

## Bundled helpers (preferred — fast, no navigation timeouts, masked)
```python
import sys, glob, os; sys.path[:0] = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\hermes\skills\th-legal")) + glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\hermes\profiles\*\skills\th-legal")); import th_tools as th
m = th.platform_claim_map(234, 1625, 1675)   # {map:{claimNo: claimId}, missing, pages, failed_pages}
print(th.platform_text(f"/claim/{m['map'][1630]}/studies"))   # masked page text
```
- **Claim numbers ≠ claim IDs.** The claims search box does not search by claim number. Always map
  numbers → IDs with `platform_claim_map` (it fetches every list page in the background) and save the
  map to the task folder.
- Slow pages: don't use `goto_url` + `wait_for_load` in loops (5 s command limit → stuck daemon).
  The helpers fetch pages in-page with long timeouts. If you must navigate, use
  `js("location.href='<url>'")`, then poll `document.readyState`.

## Map
| Area | URL |
|---|---|
| Dashboard (calendar, create task) | `/dashboard` |
| Departments (الادارات القانونية) | التقاضي `/1/cases` · إجراءات الإفلاس `/2/cases` · الاستشارات `/3/cases` · الدراسات والبحوث `/7/cases` · الإدارة العامة `/8/cases` · التنفيذ `/9/cases` |
| Other | الأرشيف `/archive` · جهات الاتصال `/contacts` · المراسلات `/correspondences` · الإشعارات `/notifications` |
| Personal (قسم المتابعة) | `/{userId}/my-tasks` · `/{userId}/my-files` · `/{userId}/vacations` · `/{userId}/performance` · `/hr/employee/{userId}` |
| **Case** | `/case/{id}/overview` + tabs: `procedures` (الإجراءات) · `tasks` (المهام) · `sessions` (جلسات المحكمة) · `memos` (مذكرات) · `financials` (الشؤون المالية) · `checklist` (تقدم قائمة التحقق) · `team` (الفريق القانوني) · `staff-chat` · `client-chat` · `subs` (القضايا الفرعية) · `claims` (المطالبات) |
| **Claim** (creditor claim in a bankruptcy case) | `/claim/{id}/studies` |

**Case overview**: title, العملاء الأفراد، وصف القضية، نوع القضية، الأولوية، المحامي الرئيسي، تم إنشاؤه بواسطة،
تاريخ الإنشاء، الفريق القانوني; attachments in groups ("تنظيم المستندات والأدلة"), search box
`searchTerm` (by title/description), "عرض N ملف إضافي" expands a group. Edit modal fields: `case.title`,
`case.description`, `case.client_requirements` (متطلبات العميل), `case.number`, `case.odoo_reference`.

**Claims tab** (`/case/{id}/claims?page=N`): search `claimSearch` (does not match claim numbers); can be
thousands of claims across many pages. Claim number shown as `#NNNN` near each `/claim/{id}/studies` link —
use `th.platform_claim_map`.

**Claim page** (`/claim/{id}/studies`): "معلومات عن المطالبة" = الدائن، رقم المطالبة، القضية، مبلغ المطالبة،
تاريخ الإنشاء، تم إنشاؤه بواسطة. "مرفقات المطالبة" = attachment groups, typically:
المستندات الأولية المستلمة من الدائن · المستندات مدمجة (merged PDF) · اثبات التبليغ · طلب النواقص ·
إيميل طلب النواقص · النواقص المستلمة من الدائن · النواقص المرسلة من الدائن · رد المدين.
Each file card: file name, size, type, "منذ …", "تم الرفع بواسطة". View = `wire:click="viewAttachment(<id>)"`
(opens a viewer modal). Study steps: modal with `stepForm.status` / `stepForm.notes`, checklist items
(عناصر قائمة التحقق, `addChecklistItem`), save = `saveStep`.

Typical claim workflow seen on the platform: creditor documents received → review → "طلب النواقص"
(request missing items, + email) → missing items received → documents merged into one PDF
("المستندات مدمجة", e.g. `<claimNo> مدمج.pdf`) → notification proof (اثبات التبليغ) → debtor reply (رد المدين).

## Reading a page (privacy-safe)
Prefer `th.platform_text(url)` (masked). For the structured view (label: value lines, attachment groups,
file cards with `attachment_id`s) on the currently open page:
```python
# inside browser_exec, after loading th_tools (above)
from pathlib import Path
print(th.mask(js(Path(th.__file__).with_name("th-platform").joinpath("scripts", "page_extract.js").read_text(encoding="utf-8"))))
```
Never dump `document.body.innerHTML`. Never take screenshots of client data.

## Downloading attachments
1. Open the viewer by clicking the card's view button:
   `js("[...document.querySelectorAll('button,a,div,span')].find(e => (e.getAttribute('wire:click')||'') === 'viewAttachment(<id>)').click()")`
2. Read the file URL from the opened modal (`iframe[src]`, `embed[src]`, `a[href][download]`, or `img[src]`).
3. Fetch it with the logged-in session and save locally (no third party involved):
```python
import base64, pathlib
b64 = js("""(async () => { const r = await fetch(%r, {credentials: 'include'});
  const u = new Uint8Array(await r.arrayBuffer()); let s = '';
  for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
  return btoa(s); })()""" % file_url)
pathlib.Path(dest).write_bytes(base64.b64decode(b64))
```
Save into the task `in/` folder as `<claimNo>_<group>_<n>.<ext>`.

## Uploading (only with approval right before)
Click the group's add button (`addFilesToGroup('<group name>')`) or "إضافة مرفق", then set the file input:
```python
doc = cdp("DOM.getDocument", depth=-1)
node = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="input[type=file][name=newGroupFiles]")  # or attachmentFiles
cdp("DOM.setFileInputFiles", nodeId=node["nodeId"], files=[r"C:\\path\\file.pdf"])
```
Then click the confirm button (`uploadFilesToGroup` / `uploadAttachments`) and verify the file now appears.

## Learning new pages
If a task touches a page not described here, explore it read-only with `page_extract.js` (and the
`[record]`-style structural listing: tabs, labels, inputs `name=`/placeholders), then tell the user what you
learned and suggest the team lead add it to this skill (the skill is shared via the team's repository).
