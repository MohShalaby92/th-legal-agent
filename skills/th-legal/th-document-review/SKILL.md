---
name: th-document-review
description: "Use when checking, proofreading or revising legal documents against the session rules. Produces a cited findings report in Arabic."
version: 1.0.0
metadata:
  hermes:
    tags: [th-legal, proofreading, arabic, review, legal]
---

# تدقيق ومراجعة المستندات — Document checking & proofreading

Inputs: the session rules (R1…Rn from `th-session-start`), the documents in the approved range.

## Procedure per document
1. Get the file locally (platform / Drive download — `th-platform`, `th-google-drive`).
2. Extract text locally: `python ~/.hermes/profiles/th-legal/skills/th-legal/th-local-docs/scripts/extract_text.py <file>`
   (path may differ: use `$HERMES_HOME`). Personal data in the output is already tokenised.
3. If a page has no text layer (scan) → record `يحتاج OCR` and follow `th-local-docs` (OCR via iLovePDF
   only inside an approved plan).
4. Check, in this order:
   - **Session rules R1…Rn** (always first; they override the defaults below).
   - **Personal data validity** from token status: any `BAD:` → error (e.g. `⟦NID-4|BAD:checksum⟧` =
     رقم هوية غير صحيح). `~X` → likely typo of X; `≈X` → same name, different spelling; `⊂X` → name
     shortened (e.g. not the full four-part name if the rules require it); `parts=N` for name length.
   - **Consistency across documents**: the same party must carry the SAME token everywhere. Two different
     tokens for what should be one person/ID/IBAN = inconsistency → report both tokens.
   - **Dates**: Hijri/Gregorian pairs agree (state when unsure; don't guess conversions — say "يحتاج تحقق"),
     date order is logical (issue before expiry, claim after judgment …).
   - **Amounts**: digits vs written words (تفقيط) agree; totals add up; currency stated.
   - **Arabic language**: spelling (همزات، التاء المربوطة/الهاء، الألف المقصورة/الياء)، grammar, legal
     phrasing, punctuation, repeated words, numbering of clauses, references to articles/attachments
     that exist.
   - **Formal elements** when the rules ask: letterhead, signatures/stamps mentioned, page numbers,
     attachments listed vs attached.
5. Record findings in the ledger (`th-batch-range`), then move on.

## Findings format (Arabic table, one row per issue)
| # | المستند | الصفحة/الموضع | النص الحالي | المشكلة | القاعدة | التصحيح المقترح | الخطورة |
Severity: `حرج` (wrong ID/IBAN/name/amount, missing signature), `متوسط` (inconsistency, wrong date),
`طفيف` (spelling, style). Quote text with tokens as-is. Never invent page numbers; use "—" if unknown.

## Revising documents (only when the user asked for edits)
- .docx: edit a COPY (`<name>.revised.docx`) with python-docx; keep formatting; track every change in the
  report. Write tokens where personal data goes; then call `pii_render` on the copy to produce the real-value
  file. Never overwrite the original.
- PDF: use iLovePDF (`th-ilovepdf`) — e.g. PDF→Word, edit, Word→PDF; or Edit PDF for small fixes.
- After editing, re-extract and re-check the edited file. Report "تم التحقق بعد التعديل".

## Final report
Write `~/TH-Work/<task>/report.md` (tokens), then `pii_render` → `report.final.md`, and tell the user the
path. Summary first: documents checked / with errors / critical count; then the table; then items not
processed and why.
