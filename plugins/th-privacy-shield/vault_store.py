"""Encrypted on-disk persistence for the PII vault (Windows DPAPI, current-user scope).

The vault maps tokens back to real values so the agent can act on them locally. It is the
only place (besides the user's own documents) where raw values are stored by the agent.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path


def hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def vault_path() -> Path:
    p = hermes_home() / "local" / "th-privacy"
    p.mkdir(parents=True, exist_ok=True)
    return p / "vault.bin"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    src, out = _blob(data), _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if protect:
        ok = fn(ctypes.byref(src), "th-privacy", None, None, None, 0x01, ctypes.byref(out))
    else:
        ok = fn(ctypes.byref(src), None, None, None, None, 0x01, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI call failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def _encrypt(b: bytes) -> bytes:
    if sys.platform == "win32":
        return b"DPAPI1" + _dpapi(b, True)
    return b"PLAIN1" + b  # non-Windows: rely on 0600 file permissions


def _decrypt(b: bytes) -> bytes:
    if b.startswith(b"DPAPI1"):
        return _dpapi(b[6:], False)
    if b.startswith(b"PLAIN1"):
        return b[6:]
    raise ValueError("unknown vault format")


def load() -> dict:
    p = vault_path()
    if not p.exists():
        return {}
    return json.loads(_decrypt(p.read_bytes()).decode("utf-8"))


def save(data: dict) -> None:
    p = vault_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(_encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8")))
    if sys.platform != "win32":
        os.chmod(tmp, 0o600)
    os.replace(tmp, p)
