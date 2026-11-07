---
name: th-batch-range
description: "Use when the user gives a range or a list of items to process. Ledger-driven loop that does not stop until every item is done."
version: 1.0.0
metadata:
  hermes:
    tags: [th-legal, batch, range, ledger]
---

# العمل على نطاق كامل — Finish the whole range

## Setup (once, after the plan is approved)
1. Task folder: `~/TH-Work/<YYYY-MM-DD>_<short-task-name>/` with `in/` (downloads), `out/` (results).
2. Expand the range into concrete item IDs (claim numbers, file names, Drive file IDs …). If the range
   comes from a platform list, read the list page(s) and collect IDs — paginate until the end.
   Save them to `items.txt` and init the ledger:
   `python <skill_dir>/scripts/ledger.py init ~/TH-Work/<task> --from-file ~/TH-Work/<task>/items.txt`
   Tell the user the total count ("سأعمل على 48 عنصرًا").

## Loop
```
while true:
  item = ledger.py next <task>      # "DONE" -> exit loop
  process item (download → extract → check → write findings to out/<item>.md)
  ledger.py mark <task> <item> ok|issues|failed|skipped "<short reason>"
```
- One item failing (unreadable file, page error, missing attachment) → mark `failed` with the reason and
  continue. Retry each failed item once at the end.
- Do NOT ask "هل أكمل؟". Do not stop after N items. Progress note to the user every ~10 items
  (one line: "تم 20/48").
- Stop early ONLY for: a needed permission not covered by the plan; the user's login expired (ask them
  to log in, then resume from `ledger.py next`); a blocker affecting all items.
- If the context gets long or the session restarts, run `ledger.py status <task>` and resume — the
  ledger is the source of truth, not your memory.

## Finish
`ledger.py status` must show `pending_count: 0`. Then merge `out/*.md` into `report.md` (summary
counts from the ledger + all findings), `pii_render` it, and give the user the path to `report.final.md`
plus the list of failed/skipped items with reasons.
