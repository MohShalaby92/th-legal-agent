"""Plugin-level tests with a fake Hermes ctx and synthetic data."""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(__file__)
os.environ["HERMES_HOME"] = tempfile.mkdtemp(prefix="th-shield-test-")
sys.path.insert(0, HERE)
from test_masker import GOOD_NID, GOOD_IBAN  # noqa: E402

PKG = os.path.join(HERE, "..", "plugins", "th-privacy-shield")
spec = importlib.util.spec_from_file_location("th_privacy_shield", os.path.join(PKG, "__init__.py"),
                                              submodule_search_locations=[PKG])
P = importlib.util.module_from_spec(spec)
sys.modules["th_privacy_shield"] = P
spec.loader.exec_module(P)


class Ctx:
    def __init__(self):
        self.mw, self.hooks, self.tools, self.cmds, self.sections = {}, {}, {}, {}, {}

    def register_middleware(self, k, f): self.mw[k] = f
    def register_hook(self, k, f): self.hooks[k] = f
    def register_tool(self, name, **kw): self.tools[name] = kw
    def register_command(self, name, f, **kw): self.cmds[name] = f
    def register_system_prompt_section(self, id, content, **kw): self.sections[id] = content


ctx = Ctx()
P.register(ctx)
NAME = "عبدالرحمن بن فيصل بن تركي المطيري"
RAW = f"الموكل: {NAME} هوية {GOOD_NID} آيبان {GOOD_IBAN} جوال 0559876543"


def dumps(o):
    return json.dumps(o, ensure_ascii=False)


def assert_clean(s):
    for raw in ("المطيري", "فيصل", GOOD_NID, GOOD_IBAN, "0559876543"):
        assert raw not in s, (raw, s[:400])


def test_anthropic_request():
    req = {
        "model": "claude-x", "system": [{"type": "text", "text": "memory: " + RAW}],
        "messages": [
            {"role": "user", "content": RAW},
            {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "plan", "signature": "SIG"},
                {"type": "tool_use", "id": "t1", "name": "browser_exec", "input": {"code": "print(1)"}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": [
                    {"type": "text", "text": RAW},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}}]}]},
        ],
        "tools": [{"name": "browser_exec", "description": "x", "input_schema": {}}],
    }
    out = ctx.mw["llm_request"](request=req)["request"]
    s = dumps(out)
    assert_clean(s)
    assert "AAAA" not in s and "SIG" in s and '"tool_use_id": "t1"' in s
    assert "⟦NID-" in s and "⟦IBAN-" in s and "⟦NAME-" in s


def test_openai_json_escaped_tool_result():
    escaped = json.dumps({"page_text": RAW})  # ensure_ascii -> \u0645 escapes
    req = {"model": "gpt-x", "messages": [
        {"role": "tool", "tool_call_id": "c1", "content": escaped},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,BBBB"}}]}]}
    out = dumps(ctx.mw["llm_request"](request=req)["request"])
    assert_clean(out)
    assert "BBBB" not in out


def test_responses_api_shape():
    req = {"model": "gpt-x", "instructions": RAW,
           "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": RAW}]},
                     {"type": "function_call_output", "call_id": "c", "output": RAW},
                     {"type": "input_file", "file_data": "CCCC"}]}
    out = dumps(ctx.mw["llm_request"](request=req)["request"])
    assert_clean(out)
    assert "CCCC" not in out


def test_tool_result_hook_then_local_unmask():
    masked = ctx.hooks["transform_tool_result"](tool_name="browser_exec", args={}, result=RAW)
    assert_clean(masked)
    nid_tok = next(t for t in masked.split() if t.startswith("⟦NID-"))
    # model writes code with the token; browser tool gets the real value back
    r = ctx.mw["tool_request"](tool_name="browser_exec", args={"code": f"fill('#id', '{nid_tok}')"})
    assert GOOD_NID in r["args"]["code"]
    # a network tool keeps the token
    assert ctx.mw["tool_request"](tool_name="web_search", args={"query": nid_tok}) is None


def test_fail_closed():
    orig = P.M.mask_text
    P.M.mask_text = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        out = dumps(ctx.mw["llm_request"](request={"model": "m", "messages": [{"role": "user", "content": RAW}]})["request"])
    finally:
        P.M.mask_text = orig
    assert_clean(out)
    assert "محجوب" in out


def test_render_and_vault_persistence():
    rep = os.path.join(os.environ["HERMES_HOME"], "report.md")
    masked = P.M.mask_text(RAW, P.VAULT)
    open(rep, "w", encoding="utf-8").write("تقرير: " + masked)
    res = json.loads(P.pii_render({"input_path": rep}))
    final = open(res["output_path"], encoding="utf-8").read()
    assert GOOD_NID in final and res["unresolved_tokens"] == 0
    # vault reloads from encrypted disk with the same tokens
    from th_privacy_shield import vault_store
    raw_bytes = open(vault_store.vault_path(), "rb").read()
    assert GOOD_NID.encode() not in raw_bytes and "المطيري".encode() not in raw_bytes
    v2 = P.M.Vault(load=vault_store.load)
    assert P.M.mask_text(RAW, v2) == masked


def test_commands():
    assert "يعمل" in ctx.cmds["pii-status"]("")
    assert "تأكيد" in ctx.cmds["pii-clear"]("")


def test_audit_log_and_leak_check():
    ctx.cmds["pii-audit"]("on")
    ctx.mw["llm_request"](request={"model": "m", "messages": [{"role": "user", "content": RAW}]})
    assert "لا تسرّب" in ctx.cmds["pii-audit"]("check")
    # simulate a leak: write a raw value straight into the audit file
    P._audit_write({"messages": [{"role": "user", "content": GOOD_NID}]})
    assert "تسرّب محتمل" in ctx.cmds["pii-audit"]("check")
    ctx.cmds["pii-audit"]("off")


if __name__ == "__main__":
    import inspect
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and inspect.isfunction(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, type(e).__name__, e)
    sys.exit(1 if fails else 0)
