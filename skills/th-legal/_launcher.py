"""TH launcher (installed to %LOCALAPPDATA%\\TH-Legal\\th.py by the setup). Finds the installed
th-legal skills and runs their th.py — so the command line is the same on every PC:

    th <command> [args]
"""
import glob
import os
import runpy
import sys

la = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/AppData/Local")
cands = [os.path.join(la, "hermes", "profiles", "th-legal", "skills", "th-legal", "th.py"),
         os.path.join(la, "hermes", "skills", "th-legal", "th.py"),
         *glob.glob(os.path.join(la, "hermes", "profiles", "*", "skills", "th-legal", "th.py"))]
for c in cands:
    if os.path.exists(c):
        sys.argv[0] = c
        runpy.run_path(c, run_name="__main__")
        break
else:
    sys.exit("TH skills not found — run TH-Legal-Setup again")
