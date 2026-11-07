---
name: th-missing-data
description: "Use when the user asks what is missing in a claim/case/file set. Compares documents and fields against a requirements list and reports gaps (النواقص)."
version: 1.0.0
metadata:
  hermes:
    tags: [th-legal, missing-documents, claims, bankruptcy, arabic]
---

# تحديد النواقص — Missing data & documents

## 1. Get the requirements list (ask; don't assume)
Ask the user which list applies, e.g. the session rules, a requirements file, the platform checklist
(`/case/{id}/checklist`, or the claim's "عناصر قائمة التحقق"), or the creditor-claim policy
("سياسة استقبال المطالبات" — often attached on the case overview). Turn it into items `Q1…Qn`, each
with: required document/field, acceptance condition (e.g. "صك ساري", "وكالة تخول المطالبة",
"آيبان باسم الدائن"), and whether it is mandatory.

## 2. Inventory what exists
- Platform claim page (`th-platform`): the info block (الدائن، رقم المطالبة، مبلغ المطالبة …) and the
  attachment groups (e.g. المستندات الأولية المستلمة من الدائن، المستندات مدمجة، اثبات التبليغ،
  طلب النواقص، النواقص المستلمة من الدائن، رد المدين). List every file by group, type and date.
- Drive folder (`th-google-drive`) if the user points there.
- Read each document's text locally (`th-local-docs`) — identify the document TYPE from its content, not
  only from its file name (file names are often wrong or generic like "مرفق 1.pdf").

## 3. Match and judge
For each Qi: `موجود ومطابق` / `موجود لكن به ملاحظة` (say what: expired, wrong name token, unsigned,
illegible scan, different amount) / `غير موجود`. Use token statuses: a claim whose IBAN token is
`BAD:checksum` or whose owner name token differs from the creditor token has a data defect even if the
document exists. Compare amounts across the claim form, invoices/judgments and the claim amount field.

## 4. Output
Per item (claim/case) a table:
| المتطلب | الحالة | الدليل (الملف/الصفحة) | الملاحظة |
then a ready-to-send Arabic "طلب نواقص" paragraph listing only the missing/defective items, polite and
specific (tokens in the agent copy; `pii_render` for the version the user sends). Do NOT send anything
or upload it anywhere unless the user explicitly asks and approves.

For a range, also produce a summary sheet (CSV, UTF-8 with BOM so Excel shows Arabic):
`claim_no, missing_count, critical, items` → `pii_render` → `missing.final.csv`.
