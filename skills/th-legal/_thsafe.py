"""Import shim for skill scripts: finds the privacy shield and exposes safe_print / mask.

Every script in skills/th-legal/*/scripts does:   from _thsafe import safe_print, mask
"""
import sys
from pathlib import Path

_p = Path(__file__).resolve()
for _up in _p.parents:
    _cand = _up / "plugins" / "th-privacy-shield"
    if (_cand / "thsafe.py").exists():
        sys.path.insert(0, str(_cand))
        break
else:  # fail closed
    raise SystemExit("[BLOCKED] privacy shield plugin not found next to this skill — refusing to print document text")

from thsafe import mask, safe_print  # noqa: E402,F401
