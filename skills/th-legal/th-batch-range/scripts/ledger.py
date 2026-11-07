"""Progress ledger for range work. Keeps going across context resets.

Usage (all paths under the task folder):
  ledger.py init  <task_dir> <item> [<item> ...]     # or: --from-file items.txt (one per line)
  ledger.py next  <task_dir>                          # prints next pending item (or DONE)
  ledger.py mark  <task_dir> <item> <ok|issues|failed|skipped> [note]
  ledger.py status <task_dir>                         # counts + remaining list
"""
import json
import sys
import time
from pathlib import Path


def path(task_dir):
    p = Path(task_dir).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p / "ledger.json"


def load(task_dir):
    p = path(task_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"items": {}, "order": []}


def save(task_dir, data):
    p = path(task_dir)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def main(argv):
    cmd, task_dir, rest = argv[1], argv[2], argv[3:]
    data = load(task_dir)
    if cmd == "init":
        if rest and rest[0] == "--from-file":
            rest = [l.strip() for l in Path(rest[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
        for it in rest:
            if it not in data["items"]:
                data["items"][it] = {"status": "pending", "note": "", "t": None}
                data["order"].append(it)
        save(task_dir, data)
        print(f"ledger: {len(data['order'])} items")
    elif cmd == "next":
        for it in data["order"]:
            if data["items"][it]["status"] == "pending":
                print(it)
                return
        print("DONE")
    elif cmd == "mark":
        it, st = rest[0], rest[1]
        data["items"].setdefault(it, {"status": "pending", "note": "", "t": None})
        if it not in data["order"]:
            data["order"].append(it)
        data["items"][it].update(status=st, note=" ".join(rest[2:]), t=time.strftime("%Y-%m-%d %H:%M"))
        save(task_dir, data)
        print(f"{it}: {st}")
    elif cmd == "status":
        counts = {}
        for it in data["order"]:
            s = data["items"][it]["status"]
            counts[s] = counts.get(s, 0) + 1
        pending = [it for it in data["order"] if data["items"][it]["status"] == "pending"]
        print(json.dumps({"total": len(data["order"]), "counts": counts, "pending": pending[:50],
                          "pending_count": len(pending)}, ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
