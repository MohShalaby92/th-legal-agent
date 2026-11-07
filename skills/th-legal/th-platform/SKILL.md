---
name: th-platform
description: "Use when working on manage.th-lawfirm.sa (cases, claims, attachments, checklists). Map of pages, safe page reading, file download/upload."
version: 1.0.0
metadata:
  hermes:
    tags: [th-legal, platform, livewire, claims, bankruptcy, arabic]
---

# منصة التميمي والحمودي — manage.th-lawfirm.sa

Laravel **Livewire + Flux UI** app, Arabic RTL. Content renders after navigation: wait 2–4 s (or poll for
an element) before reading. Actions are `wire:click` handlers, not links. Default is **read-only**:
editing, uploading, status changes, or saving on the platform need explicit approval just before the click.

## Login
The user logs in themselves (email+password or "تسجيل الدخول باستخدام جوجل") in the agent's browser
window (`browser.headed: true`). Never type credentials. If you land on `/login`, stop and ask the user to
log in, then continue. If the agent browser doesn't work for them, the fallback is Desktop app →
Settings → Browser → "use my real browser profile" (Chrome/Brave/Edge logins), which the user turns on.

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

**Claims tab** (`/case/{id}/claims`): search `claimSearch`; can be thousands of claims — paginate/scroll and
collect claim links `/claim/{id}/studies`. Claim number shown as `#NNNN` (رقم المطالبة).

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
Always read with the bundled extractor — it outputs `label: value` lines (so the privacy shield can spot
names after labels), attachment groups and file cards with `attachment_id`s:
```python
# inside browser_exec
goto_url("https://manage.th-lawfirm.sa/claim/<id>/studies"); wait_for_load(); import time; time.sleep(3)
print(js(open(r"<skill_dir>/scripts/page_extract.js", encoding="utf-8").read()))
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
