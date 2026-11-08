"""Safe output for helper scripts: everything they print is masked locally FIRST.

This is a second, independent layer: it works even if the Hermes plugin hooks are not active
in the current session. Scripts use it like:

    from thsafe import safe_print          (after adding this folder to sys.path — see find_shield())

If the masker cannot be loaded, safe_print refuses to print text (fail-closed).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    import masker as _M  # noqa: E402
    import vault_store as _S  # noqa: E402
    _VAULT = _M.Vault(store=_S.Store)
    _OK = True
except Exception as exc:  # pragma: no cover
    _OK = False
    _ERR = f"{type(exc).__name__}: {exc}"


def mask(text: str) -> str:
    if not _OK:
        return "[BLOCKED: privacy masker unavailable — output withheld]"
    return _M.mask_text(str(text), _VAULT)


def safe_print(*parts, sep: str = " ") -> None:
    out = mask(sep.join(str(p) for p in parts))
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(out)


def find_shield(start: str | os.PathLike) -> Path:
    """Locate plugins/th-privacy-shield from any script inside a Hermes home."""
    p = Path(start).resolve()
    for up in [p, *p.parents]:
        cand = up / "plugins" / "th-privacy-shield"
        if (cand / "thsafe.py").exists():
            return cand
    raise FileNotFoundError("th-privacy-shield plugin folder not found")
