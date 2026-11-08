---
name: th-session-start
description: "Use when a new session starts or the user greets. Confirm AI engine, collect the session's review rules, task and range."
version: 1.1.0
metadata:
  hermes:
    tags: [th-legal, session, onboarding, arabic]
---

# بداية الجلسة — Session start protocol

Run this at the start of EVERY new session, before any other work. Use the `clarify` tool so the
user gets clickable choices. Write in Arabic.

## 0. Privacy self-test and connection check (automatic, read-only — no permission needed)
1. `th selftest`
   - PASS: the ID and the mobile number appear as ⟦NID-n…⟧ / ⟦PHONE-n…⟧ tokens.
   - FAIL: any 10-digit ID or 05… number is visible → reply only:
     «⚠️ حماية البيانات الشخصية غير مفعّلة في هذه الجلسة. أغلق تطبيق Hermes وافتحه من جديد، وإن استمرت
     المشكلة شغّل ملف الإعداد TH-Legal-Setup مرة أخرى.» Do no other work in this session.
2. `th browser check` → JSON with `platform` and `google_drive`.
   - It starts the work browser («TH Chrome (العمل)») if it is closed — never close it yourself.
   - For each `SIGN-IN NEEDED`, ask the user to sign in in that window themselves (one short line each):
     المنصة: «سجّل الدخول إلى منصة التميمي والحمودي في نافذة "TH Chrome (العمل)"»؛
     جوجل: «سجّل الدخول بحساب جوجل الخاص بالعمل في النافذة نفسها». Run `th browser open-logins` to open
     both login pages for them. Then re-run `browser check` until both say `signed-in`.
   - Only ask for the sign-ins the task actually needs (e.g. no Google needed for a local-files task).
   - `browser: not-started` → Chrome/Edge is missing or blocked; ask the user to open the
     «TH Chrome (العمل)» shortcut on the desktop, then check again.
3. Report in ONE line, e.g. «✅ حماية البيانات تعمل · ✅ المنصة · ⚠️ جوجل: يلزم تسجيل الدخول».

## 1. Engine (المحرك)
Read the model name from your system prompt ("Model: …") and ask:

> الجلسة تعمل حاليًا على: **<model>**. هل تريد الاستمرار عليه أم التبديل؟

Choices: `الاستمرار` · `Claude Opus 5.5` · `ChatGPT Sol 5.6` · `ChatGPT Sol 6`.
- If they pick another engine: in the Hermes app click the model name at the bottom of the chat box
  (or type `/model`) and choose it. You cannot switch the model yourself.
- If no engine is signed in yet (first use): guide them in simple Arabic, one step at a time —
  Hermes app → الإعدادات (Settings) → Model/Providers → choose Anthropic (Claude) or OpenAI (ChatGPT)
  → "Sign in" → log in with THEIR OWN account in the browser window → pick the model. Never ask for a
  key or password in chat. Avoid terminal commands with these users.

## 2. Rules (قواعد التدقيق) — mandatory
Ask: "ما قواعد التدقيق والمراجعة لهذه الجلسة؟" (free text). Offer two shortcuts:
- `استخدام قواعد الجلسة السابقة`: read `~/TH-Work/rules/latest.md` if it exists, show a summary, and use
  it only after the user confirms.
- `سأكتبها الآن`.
Save the confirmed rules to `~/TH-Work/rules/<YYYY-MM-DD_HHMM>.md` and copy to `latest.md`.
Turn the rules into a numbered checklist (R1, R2, …) and show it back for confirmation. Every finding
in later reports cites the rule number it violates.

## 3. Task and range (المهمة والنطاق)
Ask what to do and exactly which items (case, claim numbers, Drive folder, file list, range). Restate the
range as a concrete list/count, e.g. "المطالبات 101–150 في القضية 234 (50 مطالبة)".

## 4. Plan + permission
Show a short numbered plan (which sites, which downloads, where files go, what gets uploaded) and ask
for approval (see SOUL "Permission"). After approval, run the whole range (skill `th-batch-range`).

## Reminders to give once per session (one short line each)
- Personal data appears to me as tokens like ⟦NID-3|ok⟧; to see real values locally: `/pii-reveal`.
- To always hide a name I missed: `/pii-name <الاسم>`.
- Please don't paste ID numbers, IBANs or names into the chat; point me to the file instead.
