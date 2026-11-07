"""th-privacy-shield — keeps personal data on the user's PC.

Layers (defence in depth):
  1. transform_tool_result : every tool result is masked before it enters the conversation
                             (so history, compression and logs hold tokens, not raw values).
  2. llm_request middleware: the FULL outbound request (system prompt, user messages, tool
                             results, tool-call args) is masked again right before it leaves
                             the machine; images / PDFs / files are stripped. If masking fails,
                             every text field is replaced with a block notice (fail-closed).
  3. tool_request middleware: tokens in the args of LOCAL tools (browser, terminal, files) are
                             swapped back to real values so the agent can still act on them.
                             Network-facing tools (web search, delegation, memory...) keep tokens.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from . import masker as M
from . import vault_store

log = logging.getLogger(__name__)

VAULT = M.Vault(load=vault_store.load, save=vault_store.save)

# Tools whose arguments may carry real values (they act on this PC / the user's own browser).
UNMASK_TOOLS = {
    "browser_exec", "browser_navigate", "browser_type", "browser_click", "browser_fill",
    "terminal", "read_file", "write_file", "patch", "search_files", "clarify",
    "computer_use", "pii_render",
}

BLOCK_NOTICE = "[محجوب: تعذّر تشغيل مرشّح الخصوصية — أُوقف الإرسال لحماية البيانات]"
IMAGE_NOTICE = "[صورة/ملف محجوب محليًا لحماية البيانات الشخصية — اقرأ النص عبر الأدوات المحلية بدلًا من الصور]"

SKIP_KEYS = {
    "model", "tools", "tool_choice", "role", "type", "id", "tool_call_id", "tool_use_id", "call_id",
    "cache_control", "stream", "stream_options", "max_tokens", "max_output_tokens", "temperature",
    "top_p", "reasoning", "reasoning_effort", "thinking", "signature", "redacted_thinking",
    "encrypted_content", "metadata", "extra_headers", "response_format", "service_tier",
    "parallel_tool_calls", "store", "include", "previous_response_id", "media_type", "status",
}
IMAGE_TYPES = {"image", "image_url", "input_image", "document", "file", "input_file", "input_audio"}


# ----------------------------------------------------------------------------- request walking
def _walk(node: Any, fn) -> Any:
    if isinstance(node, str):
        return fn(node)
    if isinstance(node, list):
        return [_walk(x, fn) for x in node]
    if isinstance(node, dict):
        t = node.get("type")
        if isinstance(t, str) and t in IMAGE_TYPES:
            return {"type": "input_text" if t.startswith("input_") else "text", "text": IMAGE_NOTICE}
        out = {}
        for k, v in node.items():
            out[k] = v if k in SKIP_KEYS else _walk(v, fn)
        return out
    return node


def _mask(s: str) -> str:
    return M.mask_text(s, VAULT)


def _audit_dir() -> Path:
    return vault_store.vault_path().parent


def _audit_on() -> bool:
    try:
        return (_audit_dir() / "AUDIT_ON").exists()
    except Exception:
        return False


def _audit_write(req: dict) -> None:
    """Append the (already masked) outbound request to a local audit file. Never leaves the PC."""
    try:
        with open(_audit_dir() / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "request": req}, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def audit_check() -> dict:
    """Search the audit log for any real value stored in the vault (i.e. a value that leaked unmasked)."""
    p = _audit_dir() / "audit.jsonl"
    if not p.exists():
        return {"requests": 0, "leaks": []}
    text = p.read_text(encoding="utf-8")
    folded = M.digits_view(text)
    leaks = []
    for e in list(VAULT.by_tid.values()):
        raw = e.raw.strip()
        if len(raw) < 5:
            continue
        probe = M.digits_view(raw)
        if raw in text or probe in folded or (e.cat != "NAME" and len(M.only_digits(raw)) >= 8 and M.only_digits(raw) in folded):
            leaks.append(e.tid)
    return {"requests": text.count("\n"), "leaks": leaks}


def on_llm_request(**kwargs):
    req = kwargs.get("request")
    if not isinstance(req, dict):
        return None
    try:
        new = _walk(req, _mask)
        if _audit_on():
            _audit_write(new)
        return {"request": new, "source": "th-privacy-shield", "reason": "masked PII"}
    except Exception as exc:  # fail closed: strip every text field
        log.error("th-privacy-shield masking failed, blocking content: %s", type(exc).__name__)
        try:
            return {"request": _walk(req, lambda s: BLOCK_NOTICE), "source": "th-privacy-shield",
                    "reason": "masking failed - content blocked"}
        except Exception:
            return {"request": {k: v for k, v in req.items() if k not in ("messages", "input", "system", "instructions")}
                    | {"messages": [{"role": "user", "content": BLOCK_NOTICE}]}}


def on_transform_tool_result(tool_name: str = "", args: Any = None, result: Any = None, **_: Any):
    if not isinstance(result, str) or not result:
        return None
    try:
        masked = M.mask_text(result, VAULT)
    except Exception:
        return BLOCK_NOTICE
    return masked if masked != result else None


def on_tool_request(**kwargs):
    name = kwargs.get("tool_name") or ""
    args = kwargs.get("args")
    if name not in UNMASK_TOOLS or not isinstance(args, dict):
        return None
    try:
        new = _walk_all(args, lambda s: M.unmask_text(s, VAULT))
    except Exception:
        return None
    if new == args:
        return None
    return {"args": new, "source": "th-privacy-shield", "reason": "restored local values"}


def _walk_all(node, fn):
    if isinstance(node, str):
        return fn(node)
    if isinstance(node, list):
        return [_walk_all(x, fn) for x in node]
    if isinstance(node, dict):
        return {k: _walk_all(v, fn) for k, v in node.items()}
    return node


# ----------------------------------------------------------------------------- local-only tools
PII_RENDER_SCHEMA = {
    "name": "pii_render",
    "description": (
        "Create a copy of a local file in which every privacy token (e.g. ⟦NID-3|ok⟧) is replaced "
        "with the real value, for the user to read or upload. Works on .txt .md .csv .json .html "
        ".xml and .docx. The real content is NEVER returned to you; you only get the output path. "
        "Use it for final reports and corrected documents the user needs with real data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "input_path": {"type": "string", "description": "File containing tokens"},
            "output_path": {"type": "string", "description": "Where to write the real-value copy (optional)"},
        },
        "required": ["input_path"],
    },
}


def pii_render(args: dict, **_: Any) -> str:
    try:
        src = Path(args.get("input_path", "")).expanduser()
        if not src.is_file():
            return json.dumps({"error": "input file not found"})
        dst = Path(args.get("output_path") or src.with_name(src.stem + ".final" + src.suffix)).expanduser()
        if src.suffix.lower() == ".docx":
            try:
                import docx  # type: ignore
            except ImportError:
                return json.dumps({"error": "python-docx not installed (pip install python-docx)"})
            d = docx.Document(str(src))

            def fix_par(p):
                full = "".join(r.text for r in p.runs)
                new = M.unmask_text(full, VAULT)
                if new != full and p.runs:
                    p.runs[0].text = new
                    for r in p.runs[1:]:
                        r.text = ""

            for p in d.paragraphs:
                fix_par(p)
            for t in d.tables:
                for row in t.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            fix_par(p)
            d.save(str(dst))
        else:
            text = src.read_text(encoding="utf-8")
            dst.write_text(M.unmask_text(text, VAULT), encoding="utf-8")
        left = len(M.TOKEN_RE.findall(dst.read_text(encoding="utf-8", errors="ignore"))) if dst.suffix.lower() != ".docx" else None
        return json.dumps({"ok": True, "output_path": str(dst), "unresolved_tokens": left})
    except Exception as exc:
        return json.dumps({"error": f"render failed: {type(exc).__name__}"})


# ----------------------------------------------------------------------------- slash commands
def _open_local(path: Path) -> None:
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception:
        pass


def cmd_reveal(raw_args: str = "", **_: Any) -> str:
    """/pii-reveal [TOKEN ...] — open a local table of tokens -> real values (auto-deleted in 10 min)."""
    want = set(re.findall(r"[A-Z]+-\d+", raw_args or ""))
    rows = []
    for e in VAULT.by_tid.values():
        if want and e.tid not in want:
            continue
        rows.append(f"<tr><td>{e.tid}</td><td>{html.escape(e.status)}</td><td>{html.escape(' '.join(e.hints))}</td>"
                    f"<td dir='auto'>{html.escape(e.raw)}</td></tr>")
    page = ("<!doctype html><meta charset='utf-8'><title>كشف الرموز</title><body dir='rtl' style='font-family:Segoe UI,Tahoma'>"
            "<h3>جدول الرموز (محلي فقط — يُحذف تلقائيًا بعد 10 دقائق)</h3><table border=1 cellpadding=6>"
            "<tr><th>الرمز</th><th>الحالة</th><th>ملاحظات</th><th>القيمة الحقيقية</th></tr>" + "".join(rows) + "</table>")
    fd, name = tempfile.mkstemp(prefix="th-reveal-", suffix=".html")
    os.close(fd)
    p = Path(name)
    p.write_text(page, encoding="utf-8")
    _open_local(p)
    threading.Timer(600, lambda: p.unlink(missing_ok=True)).start()
    return f"فُتح جدول الكشف محليًا في المتصفح ({len(rows)} رمز). لم يُرسل أي شيء للنموذج."


def cmd_add_name(raw_args: str = "", **_: Any) -> str:
    """/pii-name الاسم — always mask this name (and its spelling variants) from now on."""
    name = (raw_args or "").strip()
    if len(name) < 3:
        return "اكتب الاسم بعد الأمر، مثال: /pii-name محمد العتيبي"
    tok = VAULT.token_for("NAME", name)
    return f"تمت الإضافة. سيظهر للنموذج كـ {tok.split('|')[0]}⟧"


def cmd_clear(raw_args: str = "", **_: Any) -> str:
    if (raw_args or "").strip() != "تأكيد":
        return "سيحذف هذا جدول الرموز نهائيًا. للتأكيد اكتب: /pii-clear تأكيد"
    VAULT.clear()
    return "تم مسح جدول الرموز."


def cmd_status(raw_args: str = "", **_: Any) -> str:
    counts: dict[str, int] = {}
    bad = 0
    for e in VAULT.by_tid.values():
        counts[e.cat] = counts.get(e.cat, 0) + 1
        bad += e.status.startswith("BAD")
    summary = "، ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "لا شيء بعد"
    return f"حارس الخصوصية يعمل ✅ | الرموز: {summary} | قيم بها أخطاء تحقق: {bad}"


SYSTEM_SECTION = """\
## حارس الخصوصية (Privacy Shield) — how personal data reaches you
All personal data is replaced ON THE USER'S PC with tokens before anything is sent to you:
⟦CAT-n|status|hints⟧  e.g. ⟦NID-n|ok⟧, ⟦IBAN-n|BAD:checksum|bank=AlRajhi|~IBAN-m⟧, ⟦NAME-n|ok|parts=3|≈NAME-m⟧
(n/m stand for numbers; real tokens always carry digits, e.g. NID-7)
CAT: NID (Saudi ID, starts 1), IQAMA (starts 2), UNIFIED (700/7…), CR, IBAN, PHONE, EMAIL, PASSPORT,
NAME, ADDR (district/street), BLDG (building no, 4 digits), POSTAL (5 digits), ADDNUM (4 digits),
SHORTADDR, NUM (other long numbers; ctx=DEED/CASE/CONTRACT/ACCT/POA/ID).
status: ok = passed local format/checksum validation; BAD:<reason> = failed (report it as an error).
hints: ~X = differs from token X by 1–2 characters (likely typo of the same value);
≈X = same name as X but different spelling/hamza/taa-marbuta/diacritics; ⊂X = shorter/longer form of name X;
parts=N = number of name parts; bank=… = bank from the IBAN.
Rules: never ask the user to type real personal data into chat; refer to tokens instead. Same token =
same value everywhere. Tokens you put in browser/terminal/file tool arguments are restored to real values
locally, so you can fill forms or edit files with them. Write reports with tokens, then call pii_render
to give the user a real-value copy. Tell the user they can run /pii-reveal to view real values locally.
Images, scans and PDF attachments are stripped before reaching you — extract text locally instead.
"""


def cmd_audit(raw_args: str = "", **_: Any) -> str:
    """/pii-audit on|off|check — keep a local copy of what is sent to the AI and check it for leaks."""
    a = (raw_args or "").strip().lower()
    flag = _audit_dir() / "AUDIT_ON"
    if a == "on":
        flag.touch()
        return "تم تفعيل سجل التدقيق المحلي (لا يُرسل لأي جهة)."
    if a == "off":
        flag.unlink(missing_ok=True)
        return "تم إيقاف سجل التدقيق."
    r = audit_check()
    if r["leaks"]:
        return f"⚠️ تسرّب محتمل: {len(r['leaks'])} قيمة ظهرت بدون حجب في {r['requests']} طلب: {', '.join(r['leaks'][:20])}"
    return f"✅ لا تسرّب: فُحص {r['requests']} طلبًا مرسلًا ولم تظهر أي قيمة حقيقية من جدول الرموز."


def register(ctx):
    ctx.register_middleware("llm_request", on_llm_request)
    ctx.register_middleware("tool_request", on_tool_request)
    ctx.register_hook("transform_tool_result", on_transform_tool_result)
    ctx.register_tool(name="pii_render", toolset="th_privacy", schema=PII_RENDER_SCHEMA, handler=pii_render)
    ctx.register_command("pii-reveal", cmd_reveal, description="عرض القيم الحقيقية للرموز محليًا", args_hint="[TOKEN]")
    ctx.register_command("pii-name", cmd_add_name, description="إضافة اسم ليُحجب دائمًا", args_hint="<الاسم>")
    ctx.register_command("pii-clear", cmd_clear, description="مسح جدول الرموز", args_hint="تأكيد")
    ctx.register_command("pii-status", cmd_status, description="حالة حارس الخصوصية")
    ctx.register_command("pii-audit", cmd_audit, description="سجل تدقيق محلي لما يُرسل وفحص التسرّب", args_hint="on|off|check")
    try:
        ctx.register_system_prompt_section("th-privacy-shield", SYSTEM_SECTION, max_chars=4000)
    except Exception as exc:
        log.warning("th-privacy-shield: system prompt section not registered: %s", exc)
