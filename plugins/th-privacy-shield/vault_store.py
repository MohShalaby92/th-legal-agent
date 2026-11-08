"""Encrypted, shared on-disk store for the PII vault (Windows DPAPI, current-user scope).

The vault lives at ONE fixed per-user location — not inside a Hermes profile — so every process and
every profile on this PC (Desktop backend threads, CLI, the helper scripts) use the same tokens:
    %LOCALAPPDATA%\\TH-Privacy\\vault.bin      (override with TH_PRIVACY_DIR)
Writes are serialised with a lock file so concurrent processes merge instead of overwriting.
"""
from __future__ import annotations

import contextlib
import ctypes
import json
import os
import sys
import time
from pathlib import Path


def privacy_dir() -> Path:
    base = os.environ.get("TH_PRIVACY_DIR")
    if base:
        p = Path(base)
    elif sys.platform == "win32":
        p = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "TH-Privacy"
    else:
        p = Path.home() / ".th-privacy"
    p.mkdir(parents=True, exist_ok=True)
    return p


def vault_path() -> Path:
    return privacy_dir() / "vault.bin"


# ----------------------------------------------------------------------------- DPAPI
if sys.platform == "win32":
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _dpapi(data: bytes, protect: bool) -> bytes:
        crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32  # type: ignore[attr-defined]
        buf = ctypes.create_string_buffer(data, len(data))
        src, out = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), _Blob()
        if protect:
            ok = crypt32.CryptProtectData(ctypes.byref(src), "th-privacy", None, None, None, 0x01, ctypes.byref(out))
        else:
            ok = crypt32.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 0x01, ctypes.byref(out))
        if not ok:
            raise OSError("DPAPI call failed")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            kernel32.LocalFree(out.pbData)


def _encrypt(b: bytes) -> bytes:
    return b"DPAPI1" + _dpapi(b, True) if sys.platform == "win32" else b"PLAIN1" + b


def _decrypt(b: bytes) -> bytes:
    if b.startswith(b"DPAPI1"):
        return _dpapi(b[6:], False)
    if b.startswith(b"PLAIN1"):
        return b[6:]
    raise ValueError("unknown vault format")


# ----------------------------------------------------------------------------- lock + io
@contextlib.contextmanager
def lock(timeout: float = 10.0):
    """Cross-process exclusive lock (lock file + O_EXCL; stale locks older than 30 s are broken)."""
    lp = privacy_dir() / "vault.lock"
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            break
        except FileExistsError:
            try:
                if time.time() - lp.stat().st_mtime > 30:
                    lp.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                raise TimeoutError("vault lock busy")
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lp.unlink()
        except OSError:
            pass


def mtime() -> int:
    try:
        return vault_path().stat().st_mtime_ns
    except OSError:
        return 0


def load() -> dict:
    p = vault_path()
    if not p.exists():
        return {}
    return json.loads(_decrypt(p.read_bytes()).decode("utf-8"))


def save(data: dict) -> None:
    p = vault_path()
    tmp = p.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_bytes(_encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8")))
    if sys.platform != "win32":
        os.chmod(tmp, 0o600)
    os.replace(tmp, p)


class Store:
    """Persistence adapter used by masker.Vault (load/save/lock/mtime)."""
    load = staticmethod(load)
    save = staticmethod(save)
    lock = staticmethod(lock)
    mtime = staticmethod(mtime)
