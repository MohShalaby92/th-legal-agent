"""Work browser ("متصفح العمل") — the user's own Chrome/Edge with a separate work profile.

Why: Google refuses sign-in inside agent-launched browsers, and copies of a Chrome profile open
signed-out on Windows. A normal Chrome window with its own profile + a local debug port works:
the user signs in there by hand once, the agent attaches to it (browser.cdp_url).

  python work_browser.py status        -> is it running?            (JSON)
  python work_browser.py start         -> start it if not running   (JSON)
  python work_browser.py check         -> start if needed, then check the platform and Google
                                          sign-ins on pages that REQUIRE an account   (JSON)
Settings: %LOCALAPPDATA%\\TH-Legal\\work-browser.json  {"exe": ..., "profile_dir": ..., "port": 9222}
(written by the installer). Prints no page content — only URLs' sign-in state.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CFG = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TH-Legal" / "work-browser.json"
PLATFORM_URL = "https://manage.th-lawfirm.sa/dashboard"
DRIVE_URL = "https://drive.google.com/drive/my-drive"


def find_exe() -> str | None:
    pf, pf86, la = os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("LOCALAPPDATA", "")
    for c in (rf"{pf}\Google\Chrome\Application\chrome.exe", rf"{pf86}\Google\Chrome\Application\chrome.exe",
              rf"{la}\Google\Chrome\Application\chrome.exe", rf"{pf86}\Microsoft\Edge\Application\msedge.exe",
              rf"{pf}\Microsoft\Edge\Application\msedge.exe"):
        if Path(c).exists():
            return c
    return None


def load_cfg() -> dict:
    cfg = {}
    if CFG.exists():
        try:
            cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
        except Exception:
            cfg = {}
    cfg.setdefault("port", 9222)
    cfg.setdefault("profile_dir", str(CFG.parent / "browser"))
    if not cfg.get("exe") or not Path(cfg["exe"]).exists():
        cfg["exe"] = find_exe()
    return cfg


def _get(url: str, method: str = "GET", timeout: float = 3):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def running(cfg) -> bool:
    try:
        _get(f"http://127.0.0.1:{cfg['port']}/json/version")
        return True
    except Exception:
        return False


def start(cfg, urls=()) -> bool:
    if running(cfg):
        return True
    if not cfg.get("exe"):
        return False
    args = [cfg["exe"], f"--remote-debugging-port={cfg['port']}", "--remote-allow-origins=http://127.0.0.1",
            f"--user-data-dir={cfg['profile_dir']}", "--no-first-run", "--no-default-browser-check", *urls]
    subprocess.Popen(args, close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    for _ in range(40):
        time.sleep(0.5)
        if running(cfg):
            return True
    return False


def _final_url(cfg, url: str, wait: float = 8.0) -> str:
    base = f"http://127.0.0.1:{cfg['port']}"
    from urllib.parse import quote
    try:
        tab = _get(f"{base}/json/new?{quote(url, safe=':/?=&')}", method="PUT")
    except Exception:
        tab = _get(f"{base}/json/new?{quote(url, safe=':/?=&')}")
    tid = tab.get("id")
    final = url
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(1)
        for t in _get(f"{base}/json/list"):
            if t.get("id") == tid:
                final = t.get("url", final)
    try:
        _get(f"{base}/json/close/{tid}")
    except Exception:
        pass
    return final


def check(cfg) -> dict:
    out = {"browser": "running" if start(cfg) else "not-started", "exe": Path(cfg.get("exe") or "").name}
    if out["browser"] != "running":
        out["hint"] = "Chrome/Edge not found or could not start"
        return out
    p = _final_url(cfg, PLATFORM_URL)
    out["platform"] = "signed-in" if "manage.th-lawfirm.sa" in p and "/login" not in p else "SIGN-IN NEEDED"
    g = _final_url(cfg, DRIVE_URL)
    out["google_drive"] = "signed-in" if g.startswith("https://drive.google.com/drive") and "accounts.google.com" not in g else "SIGN-IN NEEDED"
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    cfg = load_cfg()
    if cmd == "status":
        res = {"browser": "running" if running(cfg) else "stopped", "port": cfg["port"]}
    elif cmd == "start":
        res = {"browser": "running" if start(cfg) else "not-started", "port": cfg["port"]}
    elif cmd == "check":
        res = check(cfg)
    elif cmd == "open-logins":
        start(cfg)
        for u in ("https://manage.th-lawfirm.sa/login", "https://accounts.google.com/ServiceLogin?continue=https://drive.google.com/drive/my-drive"):
            try:
                _get(f"http://127.0.0.1:{cfg['port']}/json/new?{u}", method="PUT")
            except Exception:
                pass
        res = {"opened": "login pages"}
    else:
        print(__doc__)
        return
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
