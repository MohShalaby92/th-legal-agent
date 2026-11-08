"""TH tools for browser_exec — Drive listing/download and platform claim map, privacy-safe.

Load inside browser_exec (one line, works on every member's PC):

    import sys, glob, os; sys.path[:0] = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\\hermes\\skills\\th-legal")) + glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\\hermes\\profiles\\*\\skills\\th-legal")); import th_tools as th

Then:
    th.drive_list(folder_id)                 -> list of {id, folder, num, kw, ext, size, created, modified}  (NO names)
    th.drive_find_claims(root_id, lo, hi)    -> {claim_no: folder_id} for a range (+ 'duplicates', 'missing')
    th.drive_download(file_id, dest_path)    -> bytes written (file saved under YOUR safe name)
    th.platform_claim_map(case_id, lo, hi)   -> {claim_no: claim_id} via the claims list pages (no navigation)
    th.platform_text(url)                    -> masked text of a platform page (fetched, not navigated)
    th.save_json(obj, path) / th.load_json(path)

All functions talk to the user's work browser through CDP evaluate with long timeouts (slow pages
don't hit the 5 s default) and never return item names or page text unmasked.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from _thsafe import mask  # noqa: E402  (fail-closed if the shield is missing)

_DRIVE_JS = (_HERE / "th-google-drive" / "scripts" / "drive_list.js").read_text(encoding="utf-8")
_PLATFORM = "https://manage.th-lawfirm.sa"

# Injected for tests; inside browser_exec the real helper is used.
_cdp = None


def _get_cdp():
    global _cdp
    if _cdp is None:
        from browser_harness.helpers import cdp as real
        _cdp = real
    return _cdp


# ----------------------------------------------------------------------------- tab plumbing
def _alive(target_id: str, host: str = "") -> bool:
    try:
        st = _evaluate(target_id, "document.readyState + ' ' + location.href", 6) or ""
        return st.split(" ")[0] in ("interactive", "complete") and st.split(" ", 1)[-1].startswith(host)
    except Exception:
        return False


def _tab_for(host: str, open_url: str) -> str:
    """A responsive tab on `host`. Background tabs may be frozen by Chrome, so the tab is brought to the
    front and probed; a frozen/stuck tab is replaced by a fresh one."""
    cdp = _get_cdp()
    tabs = [t for t in cdp("Target.getTargets")["targetInfos"] if t.get("type") == "page"]
    for t in reversed(tabs):
        if t.get("url", "").startswith(host):
            try:
                cdp("Target.activateTarget", targetId=t["targetId"])
            except Exception:
                pass
            if _alive(t["targetId"], host):
                return t["targetId"]
            break
    tid = cdp("Target.createTarget", url=open_url)["targetId"]
    _wait_ready(tid, 40, host)
    return tid


def _evaluate(target_id: str, expr: str, timeout: float = 180):
    cdp = _get_cdp()
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"]
    try:
        r = cdp("Runtime.evaluate", session_id=sid, _response_timeout=timeout, expression=expr,
                returnByValue=True, awaitPromise=True, timeout=int(timeout * 1000))
    finally:
        try:
            cdp("Target.detachFromTarget", sessionId=sid)
        except Exception:
            pass
    if r.get("exceptionDetails"):
        desc = (r.get("result") or {}).get("description") or r["exceptionDetails"].get("text", "")
        raise RuntimeError("page script failed: " + mask(str(desc))[:300])
    return (r.get("result") or {}).get("value")


def _wait_ready(target_id: str, timeout: float = 30, host: str = "http"):
    t0 = time.time()
    time.sleep(1)
    while time.time() - t0 < timeout:
        if _alive(target_id, host):
            return
        time.sleep(1)


def _retry(fn, attempts=3, delay=3):
    last: Exception = RuntimeError("no attempts")
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # network blips (report T7)
            last = e
            time.sleep(delay * (i + 1))
    raise last


# ----------------------------------------------------------------------------- Drive
def drive_list(folder_id: str) -> list[dict]:
    tid = _tab_for("https://drive.google.com", "https://drive.google.com/drive/my-drive")
    expr = _DRIVE_JS.replace("__PARAMS__", json.dumps({"folder": folder_id}))
    res = json.loads(_retry(lambda: _evaluate(tid, expr, 240)))
    if not res.get("ok"):
        raise RuntimeError(f"Drive listing failed: {res.get('error')} (status {res.get('status')}) — "
                           "is Google signed in in the work browser?")
    return res["items"]


def drive_find_claims(root_id: str, lo: int, hi: int) -> dict:
    items = drive_list(root_id)
    found, dup = {}, {}
    for it in items:
        if it["folder"] and it["num"] and lo <= int(it["num"]) <= hi:
            n = int(it["num"])
            if n in found:
                dup.setdefault(n, [found[n]]).append(it["id"])
            else:
                found[n] = it["id"]
    return {"total_children": len(items), "found": found, "duplicates": dup,
            "missing": [n for n in range(lo, hi + 1) if n not in found]}


def drive_download(file_id: str, dest_path: str, timeout: float = 300) -> int:
    """Download a Drive file into dest_path (choose a SAFE name: claim no + doc type, never a person's name)."""
    cdp = _get_cdp()
    dest = Path(dest_path).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".dl-{uuid.uuid4().hex[:8]}"
    tmp.mkdir()
    cdp("Browser.setDownloadBehavior", behavior="allowAndName", downloadPath=str(tmp), eventsEnabled=False)
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0&confirm=t"
    tid = cdp("Target.createTarget", url=url, background=True)["targetId"]
    try:
        t0, last = time.time(), -1
        while time.time() - t0 < timeout:
            time.sleep(1.5)
            files = [f for f in tmp.iterdir() if not f.name.endswith((".crdownload", ".tmp"))]
            if files:
                size = files[0].stat().st_size
                if size == last and size > 0:
                    os.replace(files[0], dest)
                    return size
                last = size
        raise TimeoutError("download did not finish — maybe a Google 'virus scan' page or sign-in needed")
    finally:
        try:
            cdp("Target.closeTarget", targetId=tid)
        except Exception:
            pass
        for f in tmp.iterdir():
            f.unlink(missing_ok=True)
        tmp.rmdir()


# ----------------------------------------------------------------------------- Platform
_CLAIMS_JS = r"""(async (P) => {
  const parse = html => new DOMParser().parseFromString(html, 'text/html');
  const get = async (p) => { for (let a = 0; a < 3; a++) { try { const r = await fetch(`/case/${P.caseId}/claims?page=${p}`, {credentials: 'include'});
      if (r.url.includes('/login')) return {login: true}; return {doc: parse(await r.text())}; } catch (e) { await new Promise(s => setTimeout(s, 1500)); } } return {err: true}; };
  const grab = (doc) => { const out = {}; doc.querySelectorAll('a[href*="/claim/"]').forEach(a => {
      const m0 = (a.getAttribute('href') || '').match(/\/claim\/(\d+)/); if (!m0) return;
      let el = a, m = null; for (let i = 0; i < 6 && el && !m; i++) { m = (el.textContent || '').match(/#\s?(\d+)/); el = el.parentElement; }
      if (m && !out[m[1]]) out[m[1]] = m0[1]; }); return out; };
  const first = await get(1); if (first.login) return JSON.stringify({ok: false, error: 'platform sign-in needed'});
  if (first.err) return JSON.stringify({ok: false, error: 'network'});
  let last = 1; first.doc.querySelectorAll('a[href*="page="], button[wire\\:click*="gotoPage"]').forEach(x => {
      const m = ((x.getAttribute('href') || '') + (x.getAttribute('wire:click') || '')).match(/page[=(]\D*(\d+)/i); if (m) last = Math.max(last, +m[1]); });
  const map = grab(first.doc); const pages = [...Array(last).keys()].slice(1).map(i => i + 1); const failed = [];
  for (let i = 0; i < pages.length; i += 4) { const batch = await Promise.all(pages.slice(i, i + 4).map(get));
      batch.forEach((b, j) => { if (b.doc) Object.assign(map, grab(b.doc)); else failed.push(pages[i + j]); }); }
  return JSON.stringify({ok: true, pages: last, failed, map});
})(__PARAMS__)"""


def platform_claim_map(case_id: int, lo: int | None = None, hi: int | None = None) -> dict:
    tid = _tab_for(_PLATFORM, f"{_PLATFORM}/case/{case_id}/claims")
    res = json.loads(_retry(lambda: _evaluate(tid, _CLAIMS_JS.replace("__PARAMS__", json.dumps({"caseId": case_id})), 300)))
    if not res.get("ok"):
        raise RuntimeError(res.get("error"))
    m = {int(k): int(v) for k, v in res["map"].items()}
    if lo is not None:
        m = {k: v for k, v in m.items() if lo <= k <= (hi or lo)}
    out = {"pages": res["pages"], "failed_pages": res["failed"], "map": dict(sorted(m.items()))}
    if lo is not None:
        out["missing"] = [n for n in range(lo, (hi or lo) + 1) if n not in m]
    return out


_TEXT_JS = r"""(async (P) => { const r = await fetch(P.url, {credentials: 'include'}); if (r.url.includes('/login')) return '[SIGN-IN NEEDED]';
  const d = new DOMParser().parseFromString(await r.text(), 'text/html'); d.querySelectorAll('script,style,svg,template').forEach(x => x.remove());
  return (d.querySelector('main') || d.body).innerText || (d.querySelector('main') || d.body).textContent; })(__PARAMS__)"""


def platform_text(url: str, max_chars: int = 40000) -> str:
    if url.startswith("/"):
        url = _PLATFORM + url
    tid = _tab_for(_PLATFORM, _PLATFORM + "/dashboard")
    txt = _retry(lambda: _evaluate(tid, _TEXT_JS.replace("__PARAMS__", json.dumps({"url": url})), 120)) or ""
    txt = "\n".join(l.strip() for l in txt.splitlines() if l.strip())
    return mask(txt[:max_chars])


# ----------------------------------------------------------------------------- small utils
def save_json(obj, path):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(p)


def load_json(path):
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
