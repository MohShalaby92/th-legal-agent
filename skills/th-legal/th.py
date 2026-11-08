"""TH command — one entry point for every local helper (pre-approved, read-only by design).

    th <command> [args]            (installed as %LOCALAPPDATA%\\hermes\\bin\\th and th.cmd)

  selftest                         privacy self-test (run at session start)
  browser check|start|status|open-logins
                                   the work browser (متصفح العمل) and sign-in check
  extract <file> [--dates] [--ocr auto|force|off] [--max-chars N]
                                   masked text (or dates only) from PDF/DOCX/XLSX/images, local OCR
  ledger init|next|mark|status <task_dir> ...
                                   progress ledger for range work
  paths                            where the TH skills live (for browser_exec imports)
"""
import re
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CMDS = {
    "selftest": HERE / "th-session-start" / "scripts" / "privacy_selftest.py",
    "browser": HERE / "th-session-start" / "scripts" / "work_browser.py",
    "extract": HERE / "th-local-docs" / "scripts" / "extract_text.py",
    "ledger": HERE / "th-batch-range" / "scripts" / "ledger.py",
}


def _native(arg: str) -> str:
    """bash on Windows turns ~/x into /c/Users/..; native Python needs C:/Users/.."""
    m = re.match(r"^/([a-zA-Z])/(.*)$", arg)
    return f"{m.group(1).upper()}:/{m.group(2)}" if m else arg


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "paths":
        print(HERE)
        return
    script = CMDS.get(cmd)
    if script is None:
        print(f"unknown command: {cmd}\n{__doc__}")
        sys.exit(2)
    sys.argv = [str(script), *[_native(a) for a in sys.argv[2:]]]
    sys.path.insert(0, str(script.parent))
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
