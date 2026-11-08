---
name: th-batch-range
description: "Use when the user gives a range or a list of items to process. Ledger-driven loop that does not stop until every item is done."
version: 1.1.0
metadata:
  hermes:
    tags: [th-legal, batch, range, ledger]
---

# العمل على نطاق كامل — Finish the whole range

(`th.py` = `python ~/AppData/Local/TH-Legal/th.py`, pre-approved.)

## Setup (once, after the plan is approved)
1. Task folder: `~/TH-Work/<YYYY-MM-DD>_<short-task-name>/` with `in/` (downloads), `out/` (results).
2. Expand the range into concrete item IDs (claim numbers, file names, Drive file IDs …). If the range
   comes from a platform list, read the list page(s) and collect IDs — paginate until the end.
   Save them to `items.txt` and init the ledger:
   `python ~/AppData/Local/TH-Legal/th.py ledger init ~/TH-Work/<task> --from-file ~/TH-Work/<task>/items.txt`
   Tell the user the total count ("سأعمل على 48 عنصرًا").

## Loop
```
while true:
  item = th.py ledger next <task>      # "DONE" -> exit loop
  process item (download → extract → check → write findings to out/<item>.md)
  th.py ledger mark <task> <item> ok|issues|failed|skipped "<short reason>"
```
- One item failing (unreadable file, page error, missing attachment) → mark `failed` with the reason and
  continue. Retry each failed item once at the end.
- Do NOT ask "هل أكمل؟". Do not stop after N items. Progress note to the user every ~10 items
  (one line: "تم 20/48").
- Stop early ONLY for: a needed permission not covered by the plan; the user's login expired (ask them
  to log in, then resume from `th.py ledger next`); a blocker affecting all items.
- If the context gets long or the session restarts, run `th.py ledger status <task>` and resume — the
  ledger is the source of truth, not your memory.
- Save results as you go (one file per item in `out/`, listings via `th.save_json`): a network timeout
  mid-loop must never lose finished work. Retry a failed network step up to 3 times before marking `failed`.

## Finish
`th.py ledger status` must show `pending_count: 0`. Then merge `out/*.md` into `report.md` (summary
counts from the ledger + all findings), `pii_render` it, and give the user the path to `report.final.md`
plus the list of failed/skipped items with reasons.
